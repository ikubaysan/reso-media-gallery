import os
import sys
import logging
import configparser
from typing import List, Tuple

from modules.FileServer import FileServer
from modules.FileServerAPI import FileServerAPI


class Config:
    def __init__(self, config_path: str = "config.ini"):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)

        # General settings
        self.script_dir: str = os.path.dirname(os.path.abspath(__file__))
        self.thumbnail_dir: str = self.config.get("Paths", "THUMBNAIL_DIR",
                                                  fallback=os.path.join(self.script_dir, "thumbnails"))
        self.db_path: str = self.config.get("Paths", "DB_PATH", fallback=os.path.join(self.script_dir, "thumbnails.db"))
        self.thumbnail_size: Tuple[int, int] = tuple(map(int, self.config.get("Images", "THUMBNAIL_SIZE", fallback="200,200").split(",")))
        self.max_response_part_length: int = self.config.getint("General", "MAX_LENGTH", fallback=260)

        # Server settings
        self.root_directory: str = self.config.get("Server", "ROOT_DIRECTORY", fallback=r"C:\Users\PC\Pictures")
        self.blacklisted_folders: List[str] = self.config.get("Server", "BLACKLISTED_FOLDERS",
                                                              fallback="ignore,private").split(",")
        self.allowed_extensions: List[str] = self.config.get("Server", "ALLOWED_EXTENSIONS",
                                                             fallback=".jpg,.jpeg,.png,.bmp,.webp").split(",")
        self.public_url: str = self.config.get("Server", "PUBLIC_URL", fallback="https://gallery.ikubaysan.com:8443")
        self.host: str = self.config.get("Server", "HOST", fallback="0.0.0.0")
        self.port: int = self.config.getint("Server", "PORT", fallback=8443)
        self.ssl_cert: str = self.config.get("SSL", "CERT_FILE", fallback="cert.pem")
        self.ssl_key: str = self.config.get("SSL", "KEY_FILE", fallback="key.pem")


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
    config = Config()

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
