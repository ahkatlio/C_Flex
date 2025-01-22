import os
import curses
import numpy as np

class CursesMusicUI:
    """
    Handles the curses-based UI for file selection and
    audio visualization. Relies on an AudioService instance
    to do the actual playback and FFT.
    """
    def __init__(self, audio_service):
        self.audio_service = audio_service

    def run_ui(self, stdscr):
        """
        Main curses event loop. Wrap with curses.wrapper().
        """
        curses.start_color()
        curses.use_default_colors()
        for i in range(1, 8):
            curses.init_pair(i, i, curses.COLOR_BLACK)

        curses.curs_set(0)
        stdscr.timeout(100)

        while True:
            file_path = self._browse_files(stdscr)
            if not file_path or file_path == 'back_to_main':
                curses.endwin()
                return

            if not self.audio_service.load_and_play(file_path):
                continue

            while True:
                try:
                    height, width = stdscr.getmaxyx()
                    stdscr.clear()

                    # Draw box and title
                    stdscr.attron(curses.color_pair(6))
                    stdscr.box()
                    title = f"🎵 Now Playing: {os.path.basename(file_path)}"
                    stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(2))

                    # Copy spectrum safely
                    with self.audio_service.lock:
                        vis_data = self.audio_service.visualizer_data.copy()

                    # Draw visualizer
                    self._draw_visualizer(stdscr, 3, height - 8, width - 4, vis_data)

                    # Calculate progress
                    duration = self.audio_service.duration_s
                    progress = 0.0
                    if duration > 0:
                        progress = self.audio_service.get_playback_position() / duration

                    self._draw_progress_bar(stdscr, height - 4, width, progress, duration)
                    self._draw_volume_meter(stdscr, height - 12, width - 12, self.audio_service.volume)
                    self._draw_controls(stdscr, height - 2, width)

                    # Handle input
                    c = stdscr.getch()
                    if c == ord(' '):
                        self.audio_service.pause()
                    elif c == ord('s'):
                        self.audio_service.stop()
                        break
                    elif c == ord('q'):
                        self.audio_service.stop()
                        stdscr.clear()
                        stdscr.refresh()
                        curses.endwin()
                        return
                    elif c == curses.KEY_UP:
                        self.audio_service.set_volume(self.audio_service.volume + 5)
                    elif c == curses.KEY_DOWN:
                        self.audio_service.set_volume(self.audio_service.volume - 5)

                    stdscr.refresh()

                except KeyboardInterrupt:
                    self.audio_service.stop()
                    break

    def _browse_files(self, stdscr):
        """
        Allows user to navigate directories and pick an .mp3 file.
        Returns absolute path, or None if user quits.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        selected = 0
        offset = 0

        while True:
            try:
                height, width = stdscr.getmaxyx()
                stdscr.clear()

                # Gather possible files
                try:
                    entries = os.listdir(current_dir)
                    files = [".."] + sorted(
                        [f for f in entries
                         if os.path.isdir(os.path.join(current_dir, f))
                            or f.lower().endswith('.mp3')]
                    )
                except PermissionError:
                    files = [".."]

                # Draw UI
                stdscr.attron(curses.color_pair(6))
                stdscr.box()
                header = f"🎵 Browse Music Files - {current_dir}"
                stdscr.addstr(0, (width - len(header)) // 2, header[:width - 2])

                max_display = height - 6
                for i in range(max_display):
                    idx = i + offset
                    if idx >= len(files):
                        break

                    file_name = files[idx]
                    prefix = "📁 " if os.path.isdir(os.path.join(current_dir, file_name)) else "🎵 "

                    if idx == selected:
                        stdscr.attron(curses.A_REVERSE)
                        stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")
                        stdscr.attroff(curses.A_REVERSE)
                    else:
                        stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")

                controls_text = " ↑↓: Move  |  Enter: Select  |  Q: Back "
                stdscr.addstr(height - 2, (width - len(controls_text)) // 2,
                              controls_text, curses.color_pair(3))
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

    def _draw_visualizer(self, stdscr, start_y, height, width, data: np.ndarray):
        if data is None or data.size == 0:
            return
        try:
            max_height = height - 4
            vis_width = (width - 6) // 3
            start_x = (width - vis_width * 2) // 2

            for x_idx, magnitude in enumerate(data):
                if x_idx >= vis_width:
                    break

                val = float(magnitude)
                bar_height = int(val * max_height * 2.0)
                bar_height = min(bar_height, max_height)

                for h in range(bar_height):
                    if x_idx < 15:
                        color = 4  # Bass
                    elif x_idx < 30:
                        color = 3  # Mids
                    else:
                        color = 6  # High

                    char = "█" if val > 0.7 else ("▓" if val > 0.4 else "▒")
                    stdscr.addstr(
                        start_y + max_height - h,
                        start_x + x_idx * 2,
                        char,
                        curses.color_pair(color) | curses.A_BOLD
                    )
        except curses.error:
            pass

    def _draw_progress_bar(self, stdscr, y, width, progress, duration):
        try:
            bar_width = width - 30
            filled = int(progress * bar_width)
            percentage = int(progress * 100)

            current_sec = progress * duration
            current_str = f"{int(current_sec)//60}:{int(current_sec)%60:02d}"
            total_str = f"{int(duration)//60}:{int(duration)%60:02d}"

            blocks = "▏▎▍▌▋▊▉█"
            gradient_colors = [1, 2, 3, 4, 5, 6]

            stdscr.addstr(y, 2, current_str, curses.color_pair(6))
            stdscr.addstr(y, 12, "┃", curses.color_pair(6))

            for i in range(bar_width):
                if i < filled:
                    color_idx = min(5, int(i * 6 / max(1, filled)))
                    stdscr.addstr(y, 13 + i, blocks[-1], curses.color_pair(gradient_colors[color_idx]))
                else:
                    stdscr.addstr(y, 13 + i, "░", curses.color_pair(1))

            stdscr.addstr(y, 13 + bar_width, "┃", curses.color_pair(6))
            stdscr.addstr(y, 15 + bar_width, total_str, curses.color_pair(6))

            pct_str = f" {percentage}% "
            pct_pos = 13 + min(filled, bar_width - len(pct_str))
            stdscr.addstr(y, pct_pos, pct_str, curses.color_pair(7) | curses.A_BOLD)

        except curses.error:
            pass

    def _draw_volume_meter(self, stdscr, start_y, start_x, volume):
        try:
            height = 7
            width = 3
            box_chars = {'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝', 'h': '═', 'v': '║'}

            stdscr.addstr(start_y, start_x, box_chars['tl'] + box_chars['h']*width + box_chars['tr'], curses.color_pair(6))
            for i in range(1, height - 1):
                stdscr.addstr(start_y + i, start_x, box_chars['v'], curses.color_pair(6))
                stdscr.addstr(start_y + i, start_x + width + 1, box_chars['v'], curses.color_pair(6))
            stdscr.addstr(start_y + height - 1, start_x,
                          box_chars['bl'] + box_chars['h']*width + box_chars['br'], curses.color_pair(6))

            stdscr.addstr(start_y + height - 2, start_x + 2, "VOL", curses.color_pair(6))
            vol_str = f"{volume:3d}%"
            stdscr.addstr(start_y + height - 1, start_x + 1, vol_str, curses.color_pair(7) | curses.A_BOLD)

            bar_height = height - 3
            filled = int(volume * bar_height / 200)
            for i in range(bar_height):
                h = bar_height - i - 1
                if h < filled:
                    color_val = min(6, max(1, int(6 * (h + 1) / bar_height)))
                    stdscr.addstr(start_y + 1 + i, start_x + 2, "█", curses.color_pair(color_val))
                else:
                    stdscr.addstr(start_y + 1 + i, start_x + 2, "░", curses.color_pair(1))

        except curses.error:
            pass

    def _draw_controls(self, stdscr, y, width):
        controls = [
            ("⏯️ ", "Space", "Play/Pause"),
            ("⏹️ ", "S", "Stop"),
            ("🔊", "↑↓", "Volume"),
            ("🚪", "Q", "Quit")
        ]
        x = 2
        try:
            for symbol, key, desc in controls:
                label = f"{symbol} {key}: {desc}"
                stdscr.addstr(y, x, label, curses.color_pair(3))
                x += len(label) + 3
        except curses.error:
            pass
