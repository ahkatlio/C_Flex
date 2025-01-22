import curses
import os
import time
import threading
from math import sin, pi
import inquirer
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.align import Align
import sys
import random
import numpy as np
import pyaudio

BASE = os.path.dirname(__file__)
FFMPEG_BIN = os.path.join(BASE, "ffmpeg", "bin")

# Prepend the local ffmpeg/bin to PATH (Windows pathsep is ';', but Python will handle it):
os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

LOCAL_FFMPEG   = os.path.join(BASE, "ffmpeg", "bin", "ffmpeg.exe")
LOCAL_FFPROBE  = os.path.join(BASE, "ffmpeg", "bin", "ffprobe.exe")  # if present

from pydub import AudioSegment

AudioSegment.converter = LOCAL_FFMPEG
AudioSegment.ffprobe   = LOCAL_FFPROBE

BANNER = r"""
[bold cyan]
███╗   ███╗██╗   ██╗███████╗██╗ ██████╗    ██████╗ ██╗      █████╗ ██╗   ██╗███████╗██████╗ 
████╗ ████║██║   ██║██╔════╝██║██╔════╝    ██╔══██╗██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
██╔████╔██║██║   ██║███████╗██║██║         ██████╔╝██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██║   ██║╚════██║██║██║         ██╔═══╝ ██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║╚██████╔╝███████║██║╚██████╗    ██║     ███████╗██║  ██║   ██║   ███████╗██║  ██║
╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝    ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
[/bold cyan]"""


def show_welcome_screen():
    """Show welcome screen with banner"""
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')

    console = Console()
    console.print(Panel(
        Align.center(BANNER),
        title="[bold yellow]Music Player[/bold yellow]",
        subtitle="[dim]Press Enter to start...[/dim]",
        border_style="cyan",
        padding=(1, 2),
        box=box.DOUBLE
    ))

    console.print("\n[bold green]Press Enter to continue...[/bold green]")
    input()

    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')


class AudioPlayer:
    def __init__(self):
        self.current_file = None
        self.paused = False
        self.playing = False
        self.volume = 50  # We'll do a simple software volume approach
        self.cached_duration = 0  # in seconds

        # Visualization data
        self.visualizer_data = np.zeros(50, dtype=np.float32)
        self.last_spectrum = np.zeros(50, dtype=np.float32)
        self.smoothing = 0.3
        self.bass_boost = 2.0
        self.beat_threshold = 0.6

        # PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = None

        # Threading
        self.stop_thread = threading.Event()
        self.update_thread = None
        self.lock = threading.Lock()

        # Internal buffers
        self.audio_segment = None
        self.frame_rate = 44100
        self.channels = 2
        self.sample_width = 2  # default 16-bit
        self.bytes_per_frame = self.channels * self.sample_width
        self.chunk_size = 2048  # frames per chunk
        self.playhead_frames = 0

    def _playback_loop(self):
        """
        Runs in a separate thread:
          - Feeds audio chunks to the output stream
          - Performs FFT on the same chunks
        """
        # Convert entire track to raw bytes once
        # We do software volume by scaling samples if volume < 200
        raw_data = self.audio_segment.raw_data
        total_frames = len(raw_data) // self.bytes_per_frame

        while not self.stop_thread.is_set():
            if self.paused:
                time.sleep(0.05)
                continue

            # If we reached the end, stop
            if self.playhead_frames >= total_frames:
                break

            # Grab the next chunk
            start_frame = self.playhead_frames
            end_frame = min(self.playhead_frames + self.chunk_size, total_frames)
            chunk_frames = end_frame - start_frame

            start_byte = start_frame * self.bytes_per_frame
            end_byte = end_frame * self.bytes_per_frame

            data_chunk = raw_data[start_byte:end_byte]

            # Convert to NumPy array for FFT, volume scaling
            # Our sample_width=2 means 16-bit signed
            # We'll convert it to float32 for processing
            chunk_array = np.frombuffer(data_chunk, dtype=np.int16).astype(np.float32)

            # Do a simple software volume by scaling
            # volume range is [0..200], so 100 is "normal"
            volume_scale = self.volume / 100.0
            chunk_array *= volume_scale

            # Write the scaled chunk to PyAudio
            # Convert back to int16
            chunk_int16 = chunk_array.astype(np.int16).tobytes()
            if self.stream is not None:
                self.stream.write(chunk_int16)

            # If stereo, mix down to mono for FFT
            if self.channels == 2:
                chunk_array = chunk_array.reshape(-1, 2).mean(axis=1)

            # Compute FFT for visualization
            fft_result = np.abs(np.fft.fft(chunk_array)[:len(chunk_array) // 2])
            spectrum = fft_result[:50]  # keep first 50 bins

            if len(spectrum) > 0 and np.max(spectrum) > 0:
                spectrum = spectrum / np.max(spectrum)

            # Smooth with previous
            spectrum = (spectrum * self.smoothing) + (self.last_spectrum * (1 - self.smoothing))
            self.last_spectrum = spectrum.copy()

            # Bass boost
            spectrum[:15] *= self.bass_boost
            # Trivial "beat" check
            if np.mean(spectrum[:10]) > self.beat_threshold:
                spectrum *= 1.2

            with self.lock:
                self.visualizer_data = spectrum

            # Advance playhead
            self.playhead_frames += chunk_frames

        # End of track or stop triggered
        self.playing = False
        self.paused = False
        self.stop_stream()

    def play(self, file_path=None):
        """Start playing the given file (MP3)."""
        if file_path:
            self.stop()  # stop any previous playback

            self.current_file = os.path.abspath(file_path)
            try:
                # Decode entire MP3 with pydub
                self.audio_segment = AudioSegment.from_file(self.current_file,
                                                            format="mp3",
                                                            ffmpeg_path=LOCAL_FFMPEG,
                                                            ffprobe_path=LOCAL_FFPROBE
                                                            )
                self.channels = self.audio_segment.channels
                self.frame_rate = self.audio_segment.frame_rate
                self.sample_width = self.audio_segment.sample_width
                self.bytes_per_frame = self.channels * self.sample_width

                # Duration in seconds
                self.cached_duration = len(self.audio_segment) / 1000.0

                # Open a PyAudio stream for playback
                self.stream = self.p.open(
                    format=self.p.get_format_from_width(self.sample_width),
                    channels=self.channels,
                    rate=self.frame_rate,
                    output=True
                )

                # Reset states
                self.playing = True
                self.paused = False
                self.playhead_frames = 0
                self.stop_thread.clear()

                # Start background thread to feed audio + do FFT
                self.update_thread = threading.Thread(target=self._playback_loop)
                self.update_thread.daemon = True
                self.update_thread.start()

                return True
            except Exception as e:
                print(f"Error loading file: {e}")
                self.current_file = None
                return False
        return False

    def pause(self):
        """Toggle pause."""
        if self.playing:
            self.paused = not self.paused

    def stop(self):
        """Stop playback."""
        if self.playing or self.paused:
            self.stop_thread.set()
            if self.update_thread:
                self.update_thread.join()
            self.stop_stream()
            self.playing = False
            self.paused = False
            with self.lock:
                self.visualizer_data[:] = 0

    def stop_stream(self):
        """Close PyAudio stream if open."""
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def get_position(self):
        """Return current playback time in seconds."""
        if not self.playing and not self.paused:
            return 0

        # If we know how many frames we've played, that’s our position
        return self.playhead_frames / float(self.frame_rate) if self.frame_rate else 0

    def set_volume(self, volume):
        """Set volume [0..200], software scaling."""
        self.volume = max(0, min(200, volume))

    def cleanup(self):
        """Cleanup resources."""
        self.stop()
        if self.p is not None:
            self.p.terminate()
            self.p = None


def draw_visualizer(stdscr, y, height, width, data):
    if data is None or not isinstance(data, np.ndarray) or len(data) == 0:
        return

    try:
        max_height = height - 4
        vis_width = (width - 6) // 3
        start_x = (width - vis_width * 2) // 2

        for x, magnitude in enumerate(data):
            if x >= vis_width:
                break

            try:
                magnitude_val = float(magnitude)
                bar_height = int(magnitude_val * max_height * 2.0)
                bar_height = min(bar_height, max_height)

                for h in range(bar_height):
                    # Color by frequency
                    if x < 15:  # Bass
                        color = 4
                    elif x < 30:  # Mid
                        color = 3
                    else:  # High
                        color = 6

                    char = "█" if magnitude_val > 0.7 else "▓" if magnitude_val > 0.4 else "▒"

                    stdscr.addstr(
                        y + max_height - h,
                        start_x + x * 2,
                        char,
                        curses.color_pair(color) | curses.A_BOLD
                    )
            except (ValueError, TypeError):
                continue

    except curses.error:
        pass


def draw_progress_bar(stdscr, y, width, progress, duration):
    try:
        bar_width = width - 30
        filled = int(progress * bar_width)
        percentage = int(progress * 100)

        current = f"{int(progress * duration) // 60}:{int(progress * duration) % 60:02d}"
        total = f"{int(duration) // 60}:{int(duration) % 60:02d}"

        blocks = "▏▎▍▌▋▊▉█"
        gradient_colors = [1, 2, 3, 4, 5, 6]

        stdscr.addstr(y, 2, f"{current}", curses.color_pair(6))
        stdscr.addstr(y, 12, "┃", curses.color_pair(6))

        for i in range(bar_width):
            if i < filled:
                color = gradient_colors[min(5, int(i * 6 / max(1, filled)))]
                stdscr.addstr(y, 13 + i, blocks[-1], curses.color_pair(color))
            else:
                stdscr.addstr(y, 13 + i, "░", curses.color_pair(1))

        stdscr.addstr(y, 13 + bar_width, "┃", curses.color_pair(6))
        stdscr.addstr(y, 15 + bar_width, f"{total}", curses.color_pair(6))

        percentage_str = f" {percentage}% "
        percentage_pos = 13 + min(filled, bar_width - len(percentage_str))
        stdscr.addstr(y, percentage_pos, percentage_str,
                      curses.color_pair(7) | curses.A_BOLD)

    except curses.error:
        pass


def draw_controls(stdscr, y, width):
    controls = [
        ("⏯️ ", "Space", "Play/Pause"),
        ("⏹️ ", "S", "Stop"),
        ("🔊", "↑↓", "Volume"),
        ("🚪", "Q", "Quit")
    ]

    x = 2
    try:
        for symbol, key, action in controls:
            stdscr.addstr(y, x, f"{symbol} {key}: {action}", curses.color_pair(3))
            x += len(f"{symbol} {key}: {action}") + 3
    except curses.error:
        pass


def draw_volume_meter(stdscr, y, x, volume):
    try:
        height = 7
        width = 3

        box_chars = {'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
                     'h': '═', 'v': '║'}

        stdscr.addstr(y, x, box_chars['tl'] + box_chars['h'] * width + box_chars['tr'], curses.color_pair(6))
        for i in range(1, height - 1):
            stdscr.addstr(y + i, x, box_chars['v'], curses.color_pair(6))
            stdscr.addstr(y + i, x + width + 1, box_chars['v'], curses.color_pair(6))
        stdscr.addstr(y + height - 1, x, box_chars['bl'] + box_chars['h'] * width + box_chars['br'],
                      curses.color_pair(6))

        stdscr.addstr(y + height - 2, x + 2, "VOL", curses.color_pair(6))
        vol_str = f"{volume:3d}%"
        stdscr.addstr(y + height - 1, x + 1, vol_str, curses.color_pair(7) | curses.A_BOLD)

        bar_height = height - 3
        filled = int(volume * bar_height / 200)
        for i in range(bar_height):
            h = bar_height - i - 1
            if h < filled:
                color = min(6, max(1, int(6 * (h + 1) / bar_height)))
                stdscr.addstr(y + 1 + i, x + 2, "█", curses.color_pair(color))
            else:
                stdscr.addstr(y + 1 + i, x + 2, "░", curses.color_pair(1))

    except curses.error:
        pass


def play_audio_ui(stdscr, player):
    curses.start_color()
    curses.use_default_colors()
    for i in range(1, 8):
        curses.init_pair(i, i, curses.COLOR_BLACK)

    curses.curs_set(0)
    stdscr.timeout(100)

    while True:
        file_path = browse_files(stdscr)
        if not file_path or file_path == 'back_to_main':
            curses.endwin()
            return

        if not player.play(file_path):
            continue

        while True:
            try:
                height, width = stdscr.getmaxyx()
                stdscr.clear()

                stdscr.attron(curses.color_pair(6))
                stdscr.box()
                title = f"🎵 Now Playing: {os.path.basename(file_path)}"
                stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(2))

                with player.lock:
                    vis_data = player.visualizer_data.copy()

                draw_visualizer(stdscr, 3, height - 8, width - 4, vis_data)

                if player.cached_duration > 0:
                    progress = player.get_position() / player.cached_duration
                else:
                    progress = 0.0

                draw_progress_bar(stdscr, height - 4, width, progress, player.cached_duration)
                draw_volume_meter(stdscr, height - 12, width - 12, player.volume)
                draw_controls(stdscr, height - 2, width)

                c = stdscr.getch()
                if c == ord(' '):
                    player.pause()
                elif c == ord('s'):
                    player.stop()
                    break
                elif c == ord('q'):
                    player.stop()
                    stdscr.clear()
                    stdscr.refresh()
                    curses.endwin()
                    return
                elif c == curses.KEY_UP:
                    player.set_volume(player.volume + 5)
                elif c == curses.KEY_DOWN:
                    player.set_volume(player.volume - 5)

                stdscr.refresh()

            except KeyboardInterrupt:
                player.stop()
                break


def browse_files(stdscr):
    # Same file-browsing code as before
    current_dir = os.path.dirname(os.path.abspath(__file__))
    selected = 0
    offset = 0

    while True:
        try:
            height, width = stdscr.getmaxyx()
            stdscr.clear()

            try:
                entries = os.listdir(current_dir)
                files = [".."] + sorted(
                    [f for f in entries
                     if os.path.isdir(os.path.join(current_dir, f)) or f.lower().endswith('.mp3')]
                )
            except PermissionError:
                files = [".."]

            stdscr.attron(curses.color_pair(6))
            stdscr.box()
            header = f"🎵 Browse Music Files - {current_dir}"
            stdscr.addstr(0, (width - len(header)) // 2, header[:width - 2])

            max_display = height - 6
            for i in range(max_display):
                idx = i + offset
                if idx >= len(files):
                    break

                file = files[idx]
                prefix = "📁 " if os.path.isdir(os.path.join(current_dir, file)) else "🎵 "

                if idx == selected:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(i + 2, 2, f"{prefix}{file[:width - 6]}")
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(i + 2, 2, f"{prefix}{file[:width - 6]}")

            controls = " ↑↓: Move  |  Enter: Select  |  Q: Back "
            stdscr.addstr(height - 2, (width - len(controls)) // 2, controls, curses.color_pair(3))

            stdscr.refresh()

            c = stdscr.getch()
            if c == curses.KEY_UP and selected > 0:
                selected -= 1
                if selected < offset:
                    offset = selected
            elif c == curses.KEY_DOWN and selected < len(files) - 1:
                selected += 1
                if selected >= offset + max_display:
                    offset = selected - max_display + 1
            elif c == ord('\n'):
                if selected >= len(files):
                    continue
                choice = files[selected]
                path = os.path.join(current_dir, choice)
                if choice == "..":
                    current_dir = os.path.dirname(current_dir)
                    selected = 0
                    offset = 0
                elif os.path.isdir(path):
                    current_dir = path
                    selected = 0
                    offset = 0
                elif choice.lower().endswith('.mp3'):
                    return path
            elif c == ord('q'):
                stdscr.clear()
                stdscr.refresh()
                curses.endwin()
                return None

        except KeyboardInterrupt:
            return None


def play_audio():
    player = AudioPlayer()
    try:
        show_welcome_screen()
        curses.wrapper(lambda stdscr: play_audio_ui(stdscr, player))
    finally:
        player.cleanup()
        curses.endwin()


if __name__ == "__main__":
    play_audio()
