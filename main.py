import os
import sys
import logging

from modules.FileServer import FileServer
from modules.FileServerAPI import FileServerAPI
from modules.Config import Config


def configure_console_logger(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


if __name__ == "__main__":
    configure_console_logger()
    logger = logging.getLogger(__name__)

    # Load configuration
    config = Config(config_path=os.path.abspath("config.ini"))

    # Ensure thumbnail directory exists
    os.makedirs(config.thumbnail_dir, exist_ok=True)

    server = FileServer(
        db_path=config.db_path,
        blacklisted_subfolders=config.blacklisted_folders,
        allowed_extensions=config.allowed_extensions,
        root_dir=config.root_directory,
        thumbnail_dir=config.thumbnail_dir,
        thumbnail_size=config.thumbnail_size,
        max_response_part_length=config.max_response_part_length
    )

    api = FileServerAPI(
        server,
        host=config.host,
        port=config.port,
        public_url=config.public_url,
        ssl_context=(config.ssl_cert, config.ssl_key)
    )

    api.run()
