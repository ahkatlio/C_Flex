import os
import curses
import logging
import numpy as np

class QuitMusicPlayerException(Exception):
    """Exception raised to quit the music player and return to the main menu."""
    pass

class CursesMusicUI:
    """
    ASCII-only version of the music UI that works in any terminal.
    Handles file selection and audio visualization.
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
        stdscr.timeout(100)
        self.logger.debug("Curses initialization complete.")

    def _playback_loop(self, stdscr, file_path):
        """Handles the playback loop for the given file path."""
        self.logger.info(f"Entering playback loop for: {file_path}")
        while True:
            try:
                # Check if auto-advance was requested
                if self.auto_advance_requested:
                    self.auto_advance_requested = False
                    next_track = self.audio_service.get_next_track()
                    if next_track:
                        self.logger.info(f"Auto-advancing to: {next_track}")
                        if self.audio_service.load_and_play(next_track):
                            file_path = next_track
                            self._show_message(stdscr, f"Now Playing: {os.path.basename(next_track)}")
                        else:
                            self.logger.warning(f"Failed to load next track: {next_track}")
                            break
                    else:
                        self.logger.info("No more tracks to play")
                        break
                
                self._handle_drawing(stdscr, file_path)
                c = stdscr.getch()
                self.logger.debug(f"Key pressed: {c}")
                if self._handle_input(c, stdscr):
                    self.logger.info("Exiting playback loop.")
                    break
            except KeyboardInterrupt:
                self.logger.warning("KeyboardInterrupt detected. Stopping audio.")
                self.audio_service.stop()
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in playback loop: {e}", exc_info=True)
                self.audio_service.stop()
                break

    def _handle_drawing(self, stdscr, file_path):
        """Manages drawing the UI elements on the screen."""
        self.logger.debug("Handling drawing.")
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        
        # Draw border
        try:
            stdscr.box()
        except curses.error:
            pass

        # Title with ASCII music note
        title = f"♪ Now Playing: {os.path.basename(file_path)}"
        if len(title) > width - 4:
            title = title[:width-7] + "..."
        
        try:
            stdscr.addstr(1, 2, title, curses.color_pair(2))
            self.logger.debug(f"Displayed title: {title}")
        except curses.error as e:
            self.logger.error(f"Curses error when adding title: {e}")

        # Get visualization data
        with self.audio_service.lock:
            vis_data = self.audio_service.visualizer_data.copy()
            self.logger.debug("Copied visualizer data.")

        # Draw visualizer
        if height > 12:
            self._draw_ascii_visualizer(stdscr, 3, height - 10, width - 4, vis_data)

        # Progress bar
        duration = self.audio_service.duration_s
        progress = 0.0
        if duration > 0:
            progress = self.audio_service.get_playback_position() / duration
            self.logger.debug(f"Playback progress: {progress * 100:.2f}%")
        else:
            self.logger.warning("Audio duration is zero or negative.")

        self._draw_ascii_progress_bar(stdscr, height - 6, width, progress, duration)
        
        # Status and controls
        self._draw_status_info(stdscr, height - 4, width)
        self._draw_ascii_controls(stdscr, height - 2, width)

        stdscr.refresh()
        self.logger.debug("Screen refreshed.")

    def _handle_input(self, c, stdscr) -> bool:
        """Processes user input during playback."""
        self.logger.debug(f"Handling input: {c}")
        if c == ord(' '):
            self.logger.info("Pause/Play toggled.")
            self.audio_service.pause()
        elif c == ord('s'):
            self.logger.info("Stop command received.")
            self.audio_service.stop()
            return True
        elif c == ord('q'):
            self.logger.info("Quit command received.")
            self.audio_service.stop()
            stdscr.clear()
            stdscr.refresh()
            curses.endwin()
            self.logger.info("Application exited by user.")
            raise QuitMusicPlayerException
        elif c == ord('r'):
            self.logger.info("Shuffle toggled.")
            shuffle_state = self.audio_service.toggle_shuffle()
            self._show_message(stdscr, f"Shuffle {'ON' if shuffle_state else 'OFF'}")
        elif c == ord('a'):
            self.logger.info("Auto-advance toggled.")
            current_auto = getattr(self.audio_service, 'auto_advance', True)
            new_auto = not current_auto
            self.audio_service.auto_advance = new_auto
            self._show_message(stdscr, f"Auto-advance {'ON' if new_auto else 'OFF'}")
        elif c == curses.KEY_RIGHT:
            self.logger.info("Next track requested.")
            next_track = self.audio_service.get_next_track()
            if next_track:
                self.audio_service.load_and_play(next_track)
                self._show_message(stdscr, f"Playing: {os.path.basename(next_track)}")
        elif c == curses.KEY_LEFT:
            self.logger.info("Previous track requested.")
            prev_track = self.audio_service.get_previous_track()
            if prev_track:
                self.audio_service.load_and_play(prev_track)
                self._show_message(stdscr, f"Playing: {os.path.basename(prev_track)}")
        elif c == curses.KEY_UP:
            self.logger.info("Increasing volume.")
            self.audio_service.set_volume(self.audio_service.volume + 5)
        elif c == curses.KEY_DOWN:
            self.logger.info("Decreasing volume.")
            self.audio_service.set_volume(self.audio_service.volume - 5)
        else:
            self.logger.debug("Unrecognized key pressed.")
        return False

    def _browse_files(self, stdscr):
        """File browser with ASCII interface."""
        current_dir = "Downloaded Audio" if os.path.exists("Downloaded Audio") else os.getcwd()
        selected_index = 0
        self.logger.info(f"Browsing files in directory: {current_dir}")

        while True:
            try:
                height, width = stdscr.getmaxyx()
                stdscr.clear()
                stdscr.box()

                # Get files
                files = self._get_files_list(current_dir)
                self.logger.debug(f"Files in {current_dir}: {len(files)} items")

                # Header
                header = f"Music Browser - {os.path.basename(current_dir)}"
                try:
                    stdscr.addstr(0, 2, header[:width-4], curses.color_pair(6))
                except curses.error:
                    pass

                # File list
                max_display = height - 6
                for i in range(max_display):
                    if i >= len(files):
                        break

                    file_name = files[i]
                    full_path = os.path.join(current_dir, file_name)
                    
                    # Determine prefix
                    if file_name == "..":
                        prefix = "[UP] "
                    elif os.path.isdir(full_path):
                        prefix = "[DIR] "
                    elif file_name.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                        prefix = "[♪] "
                    else:
                        prefix = "[FILE] "

                    display_text = f"{prefix}{file_name}"
                    if len(display_text) > width - 4:
                        display_text = display_text[:width-7] + "..."

                    try:
                        if i == selected_index:
                            stdscr.addstr(i + 2, 2, display_text, curses.color_pair(2) | curses.A_REVERSE)
                        else:
                            color = 3 if prefix == "[♪] " else 4 if prefix == "[DIR] " else 1
                            stdscr.addstr(i + 2, 2, display_text, curses.color_pair(color))
                    except curses.error:
                        pass

                # Controls
                controls_text = "UP/DOWN: Navigate | ENTER: Select | Q: Quit"
                try:
                    stdscr.addstr(height - 2, 2, controls_text[:width-4], curses.color_pair(5))
                except curses.error:
                    pass

                stdscr.refresh()

                # Handle input
                key = stdscr.getch()
                if key == curses.KEY_UP and selected_index > 0:
                    selected_index -= 1
                elif key == curses.KEY_DOWN and selected_index < len(files) - 1:
                    selected_index += 1
                elif key == ord('\n') or key == ord('\r'):
                    if selected_index < len(files):
                        choice = files[selected_index]
                        path = os.path.join(current_dir, choice)
                        
                        if choice == "..":
                            current_dir = os.path.dirname(current_dir)
                            selected_index = 0
                        elif os.path.isdir(path):
                            current_dir = path
                            selected_index = 0
                        elif choice.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
                            # Set up playlist and return selected file
                            self.audio_service.set_playlist_from_folder(path)
                            return path
                elif key == ord('q'):
                    return 'back_to_main'

            except KeyboardInterrupt:
                self.logger.warning("KeyboardInterrupt detected in file browser.")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error in file browser: {e}", exc_info=True)
                return None

    def _get_files_list(self, directory):
        """Get sorted list of directories and audio files."""
        try:
            entries = os.listdir(directory)
            audio_extensions = ('.mp3', '.wav', '.flac', '.ogg', '.m4a')
            
            # Separate directories and audio files
            dirs = [f for f in entries if os.path.isdir(os.path.join(directory, f))]
            audio_files = [f for f in entries if f.lower().endswith(audio_extensions)]
            
            # Combine with parent directory option
            files = [".."] + sorted(dirs) + sorted(audio_files)
            return files
        except (PermissionError, OSError):
            return [".."]

    def _draw_ascii_visualizer(self, stdscr, start_y, height, width, data):
        """Draw ASCII visualizer."""
        if data is None or data.size == 0:
            return
        
        try:
            max_height = height - 2
            vis_width = min(width - 4, 60)  # Limit width for better display
            
            # Sample data for visualizer bars
            step = max(1, len(data) // vis_width)
            
            for x in range(vis_width):
                if x * step >= len(data):
                    break
                    
                magnitude = float(data[x * step])
                bar_height = int(magnitude * max_height)
                
                # Choose character based on intensity
                if magnitude > 0.8:
                    char = "#"
                    color = 1  # Red
                elif magnitude > 0.6:
                    char = "="
                    color = 3  # Yellow
                elif magnitude > 0.4:
                    char = "-"
                    color = 2  # Green
                elif magnitude > 0.2:
                    char = "."
                    color = 4  # Blue
                else:
                    char = " "
                    color = 1
                
                # Draw vertical bar
                for y in range(bar_height):
                    try:
                        stdscr.addstr(start_y + max_height - y - 1, start_y + x + 2, char, curses.color_pair(color))
                    except curses.error:
                        pass
                        
        except Exception as e:
            self.logger.error(f"Error in ASCII visualizer: {e}")

    def _draw_ascii_progress_bar(self, stdscr, y, width, progress, duration):
        """Draw ASCII progress bar."""
        try:
            bar_width = width - 35
            if bar_width < 10:
                return
                
            filled = int(progress * bar_width)
            percentage = int(progress * 100)

            current_sec = progress * duration
            current_str = f"{int(current_sec)//60}:{int(current_sec)%60:02d}"
            total_str = f"{int(duration)//60}:{int(duration)%60:02d}"

            # Time display
            stdscr.addstr(y, 2, current_str, curses.color_pair(6))
            stdscr.addstr(y, 10, "|", curses.color_pair(6))

            # Progress bar
            for i in range(bar_width):
                if i < filled:
                    stdscr.addstr(y, 12 + i, "=", curses.color_pair(2))
                else:
                    stdscr.addstr(y, 12 + i, "-", curses.color_pair(1))

            # End time and percentage
            stdscr.addstr(y, 12 + bar_width + 2, f"| {total_str} ({percentage}%)", curses.color_pair(6))

        except curses.error as e:
            self.logger.error(f"Error drawing progress bar: {e}")

    def _draw_status_info(self, stdscr, y, width):
        """Draw current status information."""
        try:
            status_parts = []
            
            # Playback status
            if self.audio_service.is_paused:
                status_parts.append("PAUSED")
            else:
                status_parts.append("PLAYING")
            
            # Shuffle status
            if getattr(self.audio_service, 'shuffle_enabled', False):
                status_parts.append("SHUFFLE")
            
            # Auto-advance status
            if getattr(self.audio_service, 'auto_advance', True):
                status_parts.append("AUTO")
            
            # Track info
            current_track = getattr(self.audio_service, 'current_track_index', 0)
            total_tracks = len(getattr(self.audio_service, 'playlist', []))
            if total_tracks > 0:
                status_parts.append(f"Track {current_track + 1}/{total_tracks}")
            
            # Volume
            status_parts.append(f"Vol {self.audio_service.volume}%")
            
            status_line = " | ".join(status_parts)
            stdscr.addstr(y, 2, status_line[:width-4], curses.color_pair(5))
                
        except curses.error as e:
            self.logger.error(f"Error drawing status: {e}")

    def _draw_ascii_controls(self, stdscr, y, width):
        """Draw control instructions."""
        try:
            controls = "Space: Play/Pause | S: Stop | Q: Quit | R: Shuffle | A: Auto | Left/Right: Prev/Next"
            stdscr.addstr(y, 2, controls[:width-4], curses.color_pair(3))
        except curses.error as e:
            self.logger.error(f"Error drawing controls: {e}")

    def _show_message(self, stdscr, message, duration=1.0):
        """Show a temporary message."""
        height, width = stdscr.getmaxyx()
        msg_y = height // 2
        msg_x = max(2, (width - len(message)) // 2)
        
        try:
            stdscr.addstr(msg_y, msg_x, message, curses.color_pair(5) | curses.A_BOLD)
            stdscr.refresh()
            
            import time
            time.sleep(duration)
            
        except curses.error as e:
            self.logger.error(f"Error showing message: {e}")

    def _on_track_finished(self):
        """Callback when a track finishes playing."""
        self.logger.info("Track finished, requesting auto-advance")
        self.auto_advance_requested = True
