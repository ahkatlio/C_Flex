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