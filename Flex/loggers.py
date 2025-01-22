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


class NullLogger:
    def debug(self, *args, **kwargs):
        # Meant to be empty
        pass
    def info(self, *args, **kwargs):
        # Meant to be empty
        pass
    def warning(self, *args, **kwargs):
        # Meant to be empty
        pass
    def error(self, *args, **kwargs):
        # Meant to be empty
        pass
    def exception(self, *args, **kwargs):
        # Meant to be empty
        pass
    def critical(self, *args, **kwargs):
        # Meant to be empty
        pass
