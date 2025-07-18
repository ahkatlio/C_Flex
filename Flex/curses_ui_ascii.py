import os
import curses
import logging
import numpy as np

class QuitMusicPlayerException(Exception):
    """Exception raised to quit the music player and return to the main menu."""
    pass

class CursesMusicUI:
    """
    Handles the curses-based UI for file selection and
    audio visualization. Relies on an AudioService instance
    to do the actual playback and FFT.
    """
    def __init__(self, audio_service, logger=None):
        self.audio_service = audio_service
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.debug("CursesMusicUI initialized.")
        
        # Set up auto-advance callback
        self.audio_service.set_track_finished_callback(self._on_track_finished)
        self.auto_advance_requested = False

    def run_ui(self, stdscr):
        self.logger.info("Starting UI.")
        self._initialize_curses(stdscr)
        while True:
            file_path = self._browse_files(stdscr)
            if not file_path or file_path == 'back_to_main':
                self.logger.info("Exiting UI.")
                curses.endwin()
                return

            self.logger.info(f"Loading and playing file: {file_path}")
            if not self.audio_service.load_and_play(file_path):
                self.logger.warning(f"Failed to load and play file: {file_path}")
                continue

            self._playback_loop(stdscr, file_path)

    def _initialize_curses(self, stdscr):
        """Sets up curses color pairs, cursor, and input timeout."""
        self.logger.debug("Initializing curses.")
        curses.start_color()
        curses.use_default_colors()
        for i in range(1, 8):
            curses.init_pair(i, i, curses.COLOR_BLACK)
            self.logger.debug(f"Initialized color pair {i}.")
        curses.curs_set(0)
        stdscr.timeout(50)

    def _browse_files(self, stdscr):
        """Navigate and select files from the file system."""
        self.logger.debug("Starting file browser.")
        current_dir = os.getcwd()
        selected_index = 0

        while True:
            try:
                files = sorted([f for f in os.listdir(current_dir) if not f.startswith('.')])
                dirs = [f for f in files if os.path.isdir(os.path.join(current_dir, f))]
                audio_files = [f for f in files if f.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))]
                
                all_items = ['..'] + dirs + audio_files
                selected_index = max(0, min(selected_index, len(all_items) - 1))
                
                stdscr.clear()
                height, width = stdscr.getmaxyx()
                
                # Header
                stdscr.addstr(0, 0, f"Directory: {current_dir}", curses.color_pair(6))
                stdscr.addstr(1, 0, "Use arrow keys to navigate, Enter to select, 'q' to quit", curses.color_pair(3))
                stdscr.addstr(2, 0, "-" * (width - 1), curses.color_pair(2))
                
                # File list
                display_start = max(0, selected_index - height // 2)
                for i, item in enumerate(all_items[display_start:display_start + height - 5]):
                    y = i + 3
                    if y >= height - 2:
                        break
                    
                    actual_index = display_start + i
                    if actual_index == selected_index:
                        attr = curses.A_REVERSE
                    else:
                        attr = curses.A_NORMAL
                    
                    if item == '..':
                        prefix = "[UP] "
                        color = 5
                    elif item in dirs:
                        prefix = "[DIR] "
                        color = 4
                    else:
                        prefix = "[AUDIO] "
                        color = 2
                    
                    display_text = f"{prefix}{item}"
                    if len(display_text) > width - 2:
                        display_text = display_text[:width - 5] + "..."
                    
                    stdscr.addstr(y, 1, display_text, curses.color_pair(color) | attr)
                
                stdscr.refresh()
                
                key = stdscr.getch()
                if key == ord('q'):
                    return 'back_to_main'
                elif key == curses.KEY_UP and selected_index > 0:
                    selected_index -= 1
                elif key == curses.KEY_DOWN and selected_index < len(all_items) - 1:
                    selected_index += 1
                elif key == ord('\n') or key == ord('\r'):
                    selected_item = all_items[selected_index]
                    if selected_item == '..':
                        current_dir = os.path.dirname(current_dir)
                        selected_index = 0
                    elif selected_item in dirs:
                        current_dir = os.path.join(current_dir, selected_item)
                        selected_index = 0
                    else:
                        # Audio file selected - set up playlist
                        full_path = os.path.join(current_dir, selected_item)
                        self.audio_service.set_playlist_from_folder(current_dir, selected_item)
                        return full_path
                        
            except Exception as e:
                self.logger.error(f"Error in file browser: {e}")
                return None

    def _playback_loop(self, stdscr, file_path):
        """Main playback loop with visualization and controls."""
        self.logger.debug(f"Starting playback loop for {file_path}.")
        
        while self.audio_service.is_playing:
            try:
                self._draw_ui(stdscr, file_path)
                stdscr.refresh()
                
                key = stdscr.getch()
                if key != -1:
                    if not self._handle_input(key):
                        break
                        
                # Handle auto-advance
                if self.auto_advance_requested:
                    self.auto_advance_requested = False
                    if self.audio_service.has_next_track():
                        next_file = self.audio_service.get_next_track()
                        if next_file and self.audio_service.load_and_play(next_file):
                            file_path = next_file
                            self.logger.info(f"Auto-advanced to: {next_file}")
                        else:
                            break
                    else:
                        break
                        
            except Exception as e:
                self.logger.error(f"Error in playback loop: {e}")
                break

    def _on_track_finished(self):
        """Callback when a track finishes playing."""
        self.auto_advance_requested = True

    def _handle_input(self, key):
        """Handle user input during playback."""
        if key == ord('q'):
            self.audio_service.stop()
            return False
        elif key == ord(' '):
            self.audio_service.toggle_pause()
        elif key == ord('s'):
            self.audio_service.stop()
            return False
        elif key == ord('r'):
            # Toggle shuffle
            self.audio_service.toggle_shuffle()
        elif key == ord('a'):
            # Toggle auto-advance
            current_setting = getattr(self.audio_service, 'auto_advance_enabled', True)
            self.audio_service.auto_advance_enabled = not current_setting
        elif key == curses.KEY_LEFT:
            # Previous track
            if self.audio_service.has_previous_track():
                prev_file = self.audio_service.get_previous_track()
                if prev_file:
                    self.audio_service.load_and_play(prev_file)
        elif key == curses.KEY_RIGHT:
            # Next track
            if self.audio_service.has_next_track():
                next_file = self.audio_service.get_next_track()
                if next_file:
                    self.audio_service.load_and_play(next_file)
        return True

    def _draw_ui(self, stdscr, file_path):
        """Draw the main playback UI."""
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        # File info
        filename = os.path.basename(file_path)
        if len(filename) > width - 4:
            filename = filename[:width - 7] + "..."
        stdscr.addstr(0, 2, f"Playing: {filename}", curses.color_pair(6))
        
        # Progress bar
        progress = self.audio_service.get_position()
        duration = self.audio_service.get_duration()
        if duration > 0:
            self._draw_progress_bar(stdscr, 2, width, progress, duration)
        
        # Visualization
        if height > 10:
            self._draw_simple_visualization(stdscr, 4, height - 8, width)
        
        # Controls and status
        self._draw_controls(stdscr, height - 4, width)

    def _draw_simple_visualization(self, stdscr, start_y, viz_height, width):
        """Draw a simple ASCII visualization."""
        try:
            fft_data = self.audio_service.get_fft_data()
            if fft_data is None or len(fft_data) == 0:
                return
            
            # Simple bars using ASCII characters
            bar_width = max(1, width // 40)  # Fewer bars for better display
            step = len(fft_data) // (width // bar_width)
            
            for i in range(0, width - bar_width, bar_width):
                if i + step < len(fft_data):
                    magnitude = fft_data[i:i+step].mean() if step > 1 else fft_data[i]
                    bar_height = int(magnitude * viz_height)
                    
                    # Use simple ASCII characters
                    for y in range(viz_height):
                        if y < bar_height:
                            char = "#" if y > bar_height * 0.7 else "*" if y > bar_height * 0.4 else "."
                            color = self._get_color_for_value(y / viz_height)
                            stdscr.addstr(start_y + viz_height - y - 1, i, char, curses.color_pair(color))
                        
        except Exception as e:
            self.logger.error(f"Error drawing visualization: {e}")

    def _get_color_for_value(self, val: float) -> int:
        """Return a color pair number based on value."""
        if val > 0.8:
            return 1  # Red
        elif val > 0.6:
            return 3  # Yellow  
        elif val > 0.4:
            return 2  # Green
        elif val > 0.2:
            return 4  # Blue
        else:
            return 5  # Magenta

    def _draw_progress_bar(self, stdscr, y, width, progress, duration):
        """Draw a simple ASCII progress bar."""
        try:
            bar_width = width - 30
            filled = int(progress * bar_width)
            percentage = int(progress * 100)

            current_sec = progress * duration
            current_str = f"{int(current_sec)//60}:{int(current_sec)%60:02d}"
            total_str = f"{int(duration)//60}:{int(duration)%60:02d}"

            stdscr.addstr(y, 2, current_str, curses.color_pair(6))
            stdscr.addstr(y, 12, "|", curses.color_pair(6))

            # Progress bar with simple characters
            for i in range(bar_width):
                if i < filled:
                    stdscr.addstr(y, 14 + i, "=", curses.color_pair(2))
                else:
                    stdscr.addstr(y, 14 + i, "-", curses.color_pair(1))

            stdscr.addstr(y, 14 + bar_width + 2, f"| {total_str} ({percentage}%)", curses.color_pair(6))

        except Exception as e:
            self.logger.error(f"Error drawing progress bar: {e}")

    def _draw_controls(self, stdscr, start_y, width):
        """Draw control instructions and status."""
        try:
            # Control instructions
            controls = [
                "Space: Pause/Resume | S: Stop | Q: Quit | R: Shuffle | A: Auto-advance",
                "Left/Right: Previous/Next Track"
            ]
            
            for i, control in enumerate(controls):
                if start_y + i < stdscr.getmaxyx()[0]:
                    stdscr.addstr(start_y + i, 2, control[:width-4], curses.color_pair(3))
            
            # Status line
            status_parts = []
            
            # Playback status
            if self.audio_service.is_paused:
                status_parts.append("PAUSED")
            else:
                status_parts.append("PLAYING")
            
            # Shuffle status
            if getattr(self.audio_service, 'shuffle_enabled', False):
                status_parts.append("SHUFFLE ON")
            else:
                status_parts.append("SHUFFLE OFF")
            
            # Auto-advance status
            if getattr(self.audio_service, 'auto_advance_enabled', True):
                status_parts.append("AUTO-ADVANCE ON")
            else:
                status_parts.append("AUTO-ADVANCE OFF")
            
            # Track info
            current_track = getattr(self.audio_service, 'current_track_index', 0)
            total_tracks = len(getattr(self.audio_service, 'playlist', []))
            if total_tracks > 0:
                status_parts.append(f"Track {current_track + 1}/{total_tracks}")
            
            status_line = " | ".join(status_parts)
            if start_y + 2 < stdscr.getmaxyx()[0]:
                stdscr.addstr(start_y + 2, 2, status_line[:width-4], curses.color_pair(5))
                
        except Exception as e:
            self.logger.error(f"Error drawing controls: {e}")
