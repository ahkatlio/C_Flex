import curses

from config import show_welcome_screen
from audio_service import AudioService
from curses_ui import CursesMusicUI

import logging


def configure_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("music_player.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("MusicPlayerMain")


def run_music_player():
    """Main entry point for the music player."""
    logger = configure_logging()
    logger.info("Starting music player.")

    audio_service = AudioService(logger=logger)

    try:
        show_welcome_screen()
        curses.wrapper(lambda stdscr: CursesMusicUI(audio_service, logger=logger).run_ui(stdscr))
    except Exception:
        logger.exception("Unhandled exception occurred during music player execution")
    finally:
        # Cleanup resources when program ends
        logger.info("Cleaning up resources.")
        audio_service.cleanup()
        try:
            curses.endwin()
        except Exception:
            # If curses.endwin() fails, log a warning but continue
            logger.warning("curses.endwin() failed during cleanup.")
        logger.info("Music player has exited.")


if __name__ == "__main__":
    run_music_player()
