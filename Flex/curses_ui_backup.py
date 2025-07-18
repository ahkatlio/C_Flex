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
        self.logger =         shuffle_status = "SHUFFLE ON" if self.audio_service.is_shuffle_enabled() else "SHUFFLE OFF"
        auto_advance_status = "AUTO ON" if self.audio_service.auto_advance else "AUTO OFF"
        controls = [
            ("⏯️ ", "Space", "Play/Pause"),
            ("⏹️ ", "S", "Stop"),
            ("🔊", "↑↓", "Volume"),
            ("⏮️ ", "←", "Previous"),
            ("⏭️ ", "→", "Next"),
            ("🔀", "R", shuffle_status),
            ("🔄", "A", auto_advance_status),
            ("🚪", "Q", "Quit")
        ]logging.getLogger(self.__class__.__name__)
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
        stdscr.attron(curses.color_pair(6))
        stdscr.box()

        title = f"🎵 Now Playing: {os.path.basename(file_path)}"
        try:
            stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(2))
            self.logger.debug(f"Displayed title: {title}")
        except curses.error as e:
            self.logger.error(f"Curses error when adding title: {e}")

        with self.audio_service.lock:
            vis_data = self.audio_service.visualizer_data.copy()
            self.logger.debug("Copied visualizer data.")

        self._draw_visualizer(stdscr, 3, height - 8, width - 4, vis_data)

        duration = self.audio_service.duration_s
        progress = 0.0
        if duration > 0:
            progress = self.audio_service.get_playback_position() / duration
            self.logger.debug(f"Playback progress: {progress * 100:.2f}%")
        else:
            self.logger.warning("Audio duration is zero or negative.")

        self._draw_progress_bar(stdscr, height - 4, width, progress, duration)
        self._draw_volume_meter(stdscr, height - 12, width - 12, self.audio_service.volume)
        self._draw_controls(stdscr, height - 2, width)

        stdscr.refresh()
        self.logger.debug("Screen refreshed.")

    def _handle_input(self, c, stdscr) -> bool:
        """
        Processes user input during playback.
        Returns True if input indicates to break out of the playback loop.
        """
        self.logger.debug(f"Handling input: {c}")
        match c:
            case p if p == ord(' '):
                self.logger.info("Pause/Play toggled.")
                self.audio_service.pause()
            case s if s == ord('s'):
                self.logger.info("Stop command received.")
                self.audio_service.stop()
                return True  # Breaks the playback loop
            case q if q == ord('q'):
                self.logger.info("Quit command received.")
                self.audio_service.stop()
                stdscr.clear()
                stdscr.refresh()
                curses.endwin()
                self.logger.info("Application exited by user.")
                raise QuitMusicPlayerException  # Immediately exit the application
            case r if r == ord('r'):
                self.logger.info("Shuffle toggled.")
                shuffle_state = self.audio_service.toggle_shuffle()
                self._show_message(stdscr, f"Shuffle {'ON' if shuffle_state else 'OFF'}")
            case a if a == ord('a'):
                self.logger.info("Auto-advance toggled.")
                self.audio_service.set_auto_advance(not self.audio_service.auto_advance)
                self._show_message(stdscr, f"Auto-advance {'ON' if self.audio_service.auto_advance else 'OFF'}")
            case curses.KEY_RIGHT:
                self.logger.info("Next track requested.")
                next_track = self.audio_service.get_next_track()
                if next_track:
                    self.audio_service.load_and_play(next_track)
                    self._show_message(stdscr, f"Playing: {os.path.basename(next_track)}")
            case curses.KEY_LEFT:
                self.logger.info("Previous track requested.")
                prev_track = self.audio_service.get_previous_track()
                if prev_track:
                    self.audio_service.load_and_play(prev_track)
                    self._show_message(stdscr, f"Playing: {os.path.basename(prev_track)}")
            case curses.KEY_UP:
                self.logger.info("Increasing volume.")
                self.audio_service.set_volume(self.audio_service.volume + 5)
            case curses.KEY_DOWN:
                self.logger.info("Decreasing volume.")
                self.audio_service.set_volume(self.audio_service.volume - 5)
            case _:
                self.logger.debug("Unrecognized key pressed.")
        return False

    def _browse_files(self, stdscr):
        """
        Allows user to navigate directories and pick an .mp3 file.
        Returns the absolute path, or None if user quits.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        selected_index = 0
        offset = 0
        self.logger.info(f"Browsing files in directory: {current_dir}")

        while True:
            try:
                height, width = stdscr.getmaxyx()
                stdscr.clear()

                # 1) Get the list of files for the current directory
                files = self._get_files_list(current_dir)
                self.logger.debug(f"Files in {current_dir}: {files}")

                # 2) Draw the file browser UI
                self._draw_file_browser(
                    stdscr=stdscr,
                    current_dir=current_dir,
                    files=files,
                    selected_index=selected_index,
                    offset=offset,
                    height=height,
                    width=width
                )

                c = stdscr.getch()
                self.logger.debug(f"File browser key pressed: {c}")

                # 3) Handle the key press and update state
                result = self._handle_browser_key(
                    stdscr=stdscr,
                    key=c,
                    selected_index=selected_index,
                    offset=offset,
                    max_display=height - 6,
                    files=files,
                    current_dir=current_dir
                )

                # The handler returns a dict describing new state or an action
                if result.get("quit"):
                    self.logger.info("Quit action received from file browser.")
                    return None
                if "new_dir" in result:
                    current_dir = result["new_dir"]
                    self.logger.info(f"Changed directory to: {current_dir}")
                if "new_selected" in result:
                    selected_index = result["new_selected"]
                    self.logger.debug(f"Selected index updated to: {selected_index}")
                if "new_offset" in result:
                    offset = result["new_offset"]
                    self.logger.debug(f"Offset updated to: {offset}")
                if "mp3_path" in result:
                    self.logger.info(f"MP3 selected: {result['mp3_path']}")
                    return result["mp3_path"]

            except KeyboardInterrupt:
                self.logger.warning("KeyboardInterrupt detected in file browser.")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error in file browser: {e}", exc_info=True)
                return None

    def _get_files_list(self, directory):
        """
        Returns a sorted list of directories and .mp3 files in `directory`,
        including '..' as the first item for parent navigation.
        """
        self.logger.debug(f"Getting files list for directory: {directory}")
        try:
            entries = os.listdir(directory)
            files = [".."] + sorted(
                f for f in entries
                if os.path.isdir(os.path.join(directory, f)) or f.lower().endswith('.mp3')
            )
            self.logger.debug(f"Files list obtained: {files}")
        except PermissionError:
            self.logger.warning(f"Permission denied accessing directory: {directory}")
            files = [".."]
        except Exception as e:
            self.logger.error(f"Error accessing directory {directory}: {e}", exc_info=True)
            files = [".."]
        return files

    def _draw_file_browser(self, stdscr, current_dir, files, selected_index, offset, height, width):
        """
        Draws the file browser UI, including the header, file list, and controls.
        """
        self.logger.debug("Drawing file browser UI.")
        stdscr.attron(curses.color_pair(6))
        stdscr.box()

        header = f"🎵 Browse Music Files - {current_dir}"
        try:
            stdscr.addstr(0, (width - len(header)) // 2, header[:width - 2])
            self.logger.debug(f"Displayed header: {header}")
        except curses.error as e:
            self.logger.error(f"Curses error when adding header: {e}")

        max_display = height - 6
        for i in range(max_display):
            idx = i + offset
            if idx >= len(files):
                break

            file_name = files[idx]
            is_dir = os.path.isdir(os.path.join(current_dir, file_name))
            prefix = "📁 " if is_dir else "🎵 "

            try:
                # Draw with highlight if selected
                if idx == selected_index:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")
            except curses.error as e:
                self.logger.error(f"Curses error when adding file entry: {e}")

        controls_text = " ↑↓: Move  |  Enter: Select  |  Q: Back "
        try:
            stdscr.addstr(height - 2, (width - len(controls_text)) // 2,
                          controls_text, curses.color_pair(3))
            self.logger.debug("Displayed file browser controls.")
        except curses.error as e:
            self.logger.error(f"Curses error when adding controls: {e}")
        stdscr.refresh()

    def _handle_browser_key(self, stdscr, key, selected_index, offset, max_display, files, current_dir):
        """
        Processes the user's key press in the file browser.
        Returns a dict describing what should happen next, e.g.:
            {
              "quit": True/False,
              "new_dir": <str> (if directory changed),
              "new_selected": <int>,
              "new_offset": <int>,
              "mp3_path": <str> (if user chose an MP3)
            }
        """
        self.logger.debug(f"Handling browser key: {key}")
        match key:
            case curses.KEY_UP:
                self.logger.debug("Browser key: UP")
                return self._handle_key_up(selected_index, offset)
            case curses.KEY_DOWN:
                self.logger.debug("Browser key: DOWN")
                return self._handle_key_down(selected_index, offset, max_display, len(files))
            case k if k == ord('\n'):
                self.logger.debug("Browser key: ENTER")
                return self._handle_key_enter(files, selected_index, current_dir)
            case q if q == ord('q'):
                self.logger.debug("Browser key: Q")
                return self._handle_key_quit(stdscr)
            case _:
                self.logger.debug("Browser key: Unrecognized")
                return {}

    def _handle_key_up(self, selected_index, offset):
        result = {}
        if selected_index > 0:
            selected_index -= 1
            if selected_index < offset:
                offset = selected_index
            self.logger.debug(f"Moved selection up to index {selected_index}, offset {offset}")
        result["new_selected"] = selected_index
        result["new_offset"] = offset
        return result

    def _handle_key_down(self, selected_index, offset, max_display, files_length):
        result = {}
        if selected_index < files_length - 1:
            selected_index += 1
            if selected_index >= offset + max_display:
                offset = selected_index - max_display + 1
            self.logger.debug(f"Moved selection down to index {selected_index}, offset {offset}")
        result["new_selected"] = selected_index
        result["new_offset"] = offset
        return result

    def _handle_key_enter(self, files, selected_index, current_dir):
        result = {}
        if 0 <= selected_index < len(files):
            choice = files[selected_index]
            path = os.path.join(current_dir, choice)
            self.logger.info(f"User selected: {choice}")

            if choice == "..":
                result["new_dir"] = os.path.dirname(current_dir)
                result["new_selected"] = 0
                result["new_offset"] = 0
                self.logger.debug("Navigated to parent directory.")
            elif os.path.isdir(path):
                result["new_dir"] = path
                result["new_selected"] = 0
                result["new_offset"] = 0
                self.logger.debug(f"Entered directory: {path}")
            elif choice.lower().endswith('.mp3'):
                result["mp3_path"] = path
                self.logger.debug(f"MP3 file selected: {path}")
        else:
            self.logger.warning(f"Selected index {selected_index} out of range.")
        return result

    def _handle_key_quit(self, stdscr):
        self.logger.info("Handling quit action from file browser.")
        stdscr.clear()
        stdscr.refresh()
        curses.endwin()
        return {"quit": True}

    def _draw_visualizer(self, stdscr, start_y, height, width, data: np.ndarray):
        if data is None or data.size == 0:
            self.logger.debug("Visualizer data is empty. Skipping visualizer drawing.")
            return
        try:
            max_height = height - 4
            vis_width = (width - 6) // 3
            start_x = (width - vis_width * 2) // 2

            self.logger.debug(f"Drawing visualizer with height {height}, width {width}")

            for x_idx, magnitude in enumerate(data):
                if x_idx >= vis_width:
                    self.logger.debug(f"Reached visualizer width limit at index {x_idx}.")
                    break

                val = float(magnitude)
                # bar_height = min(int(val * max_height * 2.0), max_height)
                bar_height = min(int(val * max_height), max_height)

                # Determine color and character once per column
                color = self._get_color_for_index(x_idx)
                char = self._get_char_for_value(val)

                for h in range(bar_height):
                    try:
                        stdscr.addstr(
                            start_y + max_height - h,
                            start_x + x_idx * 2,
                            char,
                            curses.color_pair(color) | curses.A_BOLD
                        )
                    except curses.error as e:
                        self.logger.error(f"Curses error when drawing visualizer: {e}")
            self.logger.debug("Visualizer drawing complete.")
        except Exception as e:
            self.logger.error(f"Error in _draw_visualizer: {e}", exc_info=True)

    @staticmethod
    def _get_color_for_index(x_idx: int) -> int:
        """Determine color based on the index for bass, mids, or high frequencies."""
        if x_idx < 15:
            return 4  # Bass
        elif x_idx < 30:
            return 3  # Mids
        else:
            return 6  # High

    @staticmethod
    def _get_char_for_value(val: float) -> str:
        """Choose a character based on the magnitude value."""
        if val > 0.7:
            return "█"
        elif val > 0.4:
            return "▓"
        else:
            return "▒"

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

            self.logger.debug(f"Progress bar drawn: {percentage}%")
        except curses.error as e:
            self.logger.error(f"Curses error when drawing progress bar: {e}")

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

            self.logger.debug(f"Volume meter drawn: {volume}%")
        except curses.error as e:
            self.logger.error(f"Curses error when drawing volume meter: {e}")

    def _draw_controls(self, stdscr, y, width):
        shuffle_status = "🔀 ON" if self.audio_service.is_shuffle_enabled() else "🔀 OFF"
        controls = [
            ("⏯️ ", "Space", "Play/Pause"),
            ("⏹️ ", "S", "Stop"),
            ("🔊", "↑↓", "Volume"),
            ("⏮️ ", "←", "Previous"),
            ("⏭️ ", "→", "Next"),
            ("�", "R", shuffle_status),
            ("�🚪", "Q", "Quit")
        ]
        x = 2
        try:
            for symbol, key, desc in controls:
                if symbol == "🔀":
                    label = f"{symbol} {key}: {desc}"
                else:
                    label = f"{symbol} {key}: {desc}"
                stdscr.addstr(y, x, label, curses.color_pair(3))
                x += len(label) + 3
                if x >= width - 20:  # Start new line if running out of space
                    y += 1
                    x = 2
            self.logger.debug("Controls drawn.")
        except curses.error as e:
            self.logger.error(f"Curses error when drawing controls: {e}")

    def _show_message(self, stdscr, message, duration=1.5):
        """Show a temporary message on screen"""
        height, width = stdscr.getmaxyx()
        msg_y = height // 2
        msg_x = (width - len(message)) // 2
        
        try:
            # Save the current content at that position
            stdscr.attron(curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(msg_y, msg_x, message)
            stdscr.attroff(curses.color_pair(5) | curses.A_BOLD)
            stdscr.refresh()
            
            # Show message for specified duration
            import time
            time.sleep(duration)
            
        except curses.error as e:
            self.logger.error(f"Curses error when showing message: {e}")

    def _on_track_finished(self):
        """Callback method triggered when a track finishes playing"""
        self.logger.info("Track finished, requesting auto-advance")
        self.auto_advance_requested = True
