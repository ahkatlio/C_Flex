import curses

from config import show_welcome_screen
from audio_service import AudioService
from curses_ui import CursesMusicUI

def run_music_player():
    """Main entry point for the music player."""
    audio_service = AudioService()

    try:
        show_welcome_screen()
        curses.wrapper(lambda stdscr: CursesMusicUI(audio_service).run_ui(stdscr))
    finally:
        # Cleanup resources when program ends
        audio_service.cleanup()
        curses.endwin()

if __name__ == "__main__":
    run_music_player()
