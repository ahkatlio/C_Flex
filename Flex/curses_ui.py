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
        self._initialize_curses(stdscr)
        while True:
            file_path = self._browse_files(stdscr)
            if not file_path or file_path == 'back_to_main':
                curses.endwin()
                return

            if not self.audio_service.load_and_play(file_path):
                continue

            self._playback_loop(stdscr, file_path)

    @staticmethod
    def _initialize_curses(stdscr):
        """Sets up curses color pairs, cursor, and input timeout."""
        curses.start_color()
        curses.use_default_colors()
        for i in range(1, 8):
            curses.init_pair(i, i, curses.COLOR_BLACK)
        curses.curs_set(0)
        stdscr.timeout(100)

    def _playback_loop(self, stdscr, file_path):
        """Handles the playback loop for the given file path."""
        while True:
            try:
                self._handle_drawing(stdscr, file_path)
                c = stdscr.getch()
                if self._handle_input(c, stdscr):
                    break
            except KeyboardInterrupt:
                self.audio_service.stop()
                break

    def _handle_drawing(self, stdscr, file_path):
        """Manages drawing the UI elements on the screen."""
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        stdscr.attron(curses.color_pair(6))
        stdscr.box()

        title = f"🎵 Now Playing: {os.path.basename(file_path)}"
        stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(2))

        with self.audio_service.lock:
            vis_data = self.audio_service.visualizer_data.copy()

        self._draw_visualizer(stdscr, 3, height - 8, width - 4, vis_data)

        duration = self.audio_service.duration_s
        progress = 0.0
        if duration > 0:
            progress = self.audio_service.get_playback_position() / duration

        self._draw_progress_bar(stdscr, height - 4, width, progress, duration)
        self._draw_volume_meter(stdscr, height - 12, width - 12, self.audio_service.volume)
        self._draw_controls(stdscr, height - 2, width)

        stdscr.refresh()

    def _handle_input(self, c, stdscr) -> bool:
        """
        Processes user input during playback.
        Returns True if input indicates to break out of the playback loop.
        """
        match c:
            case p if p == ord(' '):
                self.audio_service.pause()
            case s if s == ord('s'):
                self.audio_service.stop()
                return True  # Breaks the playback loop
            case q if q == ord('q'):
                self.audio_service.stop()
                stdscr.clear()
                stdscr.refresh()
                curses.endwin()
                exit(0)  # Immediately exit the application
            case curses.KEY_UP:
                self.audio_service.set_volume(self.audio_service.volume + 5)
            case curses.KEY_DOWN:
                self.audio_service.set_volume(self.audio_service.volume - 5)
        return False

    def _browse_files(self, stdscr):
        """
        Allows user to navigate directories and pick an .mp3 file.
        Returns the absolute path, or None if user quits.
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        selected_index = 0
        offset = 0

        while True:
            try:
                height, width = stdscr.getmaxyx()
                stdscr.clear()

                # 1) Get the list of files for the current directory
                files = self._get_files_list(current_dir)

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
                    return None
                if "new_dir" in result:
                    current_dir = result["new_dir"]
                if "new_selected" in result:
                    selected_index = result["new_selected"]
                if "new_offset" in result:
                    offset = result["new_offset"]
                if "mp3_path" in result:
                    # The user selected an MP3 and we have a valid path
                    return result["mp3_path"]

            except KeyboardInterrupt:
                return None

        # Should never reach here due to the while True
        return None

    @staticmethod
    def _get_files_list(directory):
        """
        Returns a sorted list of directories and .mp3 files in `directory`,
        including '..' as the first item for parent navigation.
        """
        try:
            entries = os.listdir(directory)
            files = [".."] + sorted(
                f for f in entries
                if os.path.isdir(os.path.join(directory, f)) or f.lower().endswith('.mp3')
            )
        except PermissionError:
            files = [".."]
        return files

    @staticmethod
    def _draw_file_browser(stdscr, current_dir, files, selected_index, offset, height, width):
        """
        Draws the file browser UI, including the header, file list, and controls.
        """
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
            is_dir = os.path.isdir(os.path.join(current_dir, file_name))
            prefix = "📁 " if is_dir else "🎵 "

            # Draw with highlight if selected
            if idx == selected_index:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(i + 2, 2, f"{prefix}{file_name[:width - 6]}")

        controls_text = " ↑↓: Move  |  Enter: Select  |  Q: Back "
        stdscr.addstr(height - 2, (width - len(controls_text)) // 2,
                      controls_text, curses.color_pair(3))
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
        match key:
            case curses.KEY_UP:
                return self._handle_key_up(selected_index, offset)
            case curses.KEY_DOWN:
                return self._handle_key_down(selected_index, offset, max_display, len(files))
            case k if k == ord('\n'):
                return self._handle_key_enter(files, selected_index, current_dir)
            case q if q == ord('q'):
                return self._handle_key_quit(stdscr)
            case _:
                return {}

    @staticmethod
    def _handle_key_up(selected_index, offset):
        result = {}
        if selected_index > 0:
            selected_index -= 1
            if selected_index < offset:
                offset = selected_index
        result["new_selected"] = selected_index
        result["new_offset"] = offset
        return result

    @staticmethod
    def _handle_key_down(selected_index, offset, max_display, files_length):
        result = {}
        if selected_index < files_length - 1:
            selected_index += 1
            if selected_index >= offset + max_display:
                offset = selected_index - max_display + 1
        result["new_selected"] = selected_index
        result["new_offset"] = offset
        return result

    @staticmethod
    def _handle_key_enter(files, selected_index, current_dir):
        result = {}
        if 0 <= selected_index < len(files):
            choice = files[selected_index]
            path = os.path.join(current_dir, choice)

            if choice == "..":
                result["new_dir"] = os.path.dirname(current_dir)
                result["new_selected"] = 0
                result["new_offset"] = 0
            elif os.path.isdir(path):
                result["new_dir"] = path
                result["new_selected"] = 0
                result["new_offset"] = 0
            elif choice.lower().endswith('.mp3'):
                result["mp3_path"] = path
        return result

    @staticmethod
    def _handle_key_quit(stdscr):
        stdscr.clear()
        stdscr.refresh()
        curses.endwin()
        return {"quit": True}

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
                bar_height = min(int(val * max_height * 2.0), max_height)

                # Determine color and character once per column
                color = self._get_color_for_index(x_idx)
                char = self._get_char_for_value(val)

                for h in range(bar_height):
                    stdscr.addstr(
                        start_y + max_height - h,
                        start_x + x_idx * 2,
                        char,
                        curses.color_pair(color) | curses.A_BOLD
                    )
        except curses.error:
            pass

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

    @staticmethod
    def _draw_progress_bar(stdscr, y, width, progress, duration):
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

    @staticmethod
    def _draw_volume_meter(stdscr, start_y, start_x, volume):
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

    @staticmethod
    def _draw_controls(stdscr, y, width):
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
