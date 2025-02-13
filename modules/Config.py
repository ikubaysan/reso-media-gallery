import configparser
import os
from typing import List, Tuple


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
        self.media_root_directory: str = self.config.get("Server", "media_root_dirECTORY", fallback=r"C:\Users\PC\Pictures")
        self.blacklisted_folders: List[str] = self.config.get("Server", "BLACKLISTED_FOLDERS",
                                                              fallback="ignore,private").split(",")
        self.allowed_extensions: List[str] = self.config.get("Server", "ALLOWED_EXTENSIONS",
                                                             fallback=".jpg,.jpeg,.png,.bmp,.webp").split(",")
        self.public_url: str = self.config.get("Server", "PUBLIC_URL", fallback="https://gallery.ikubaysan.com:8443")
        self.host: str = self.config.get("Server", "HOST", fallback="0.0.0.0")
        self.port: int = self.config.getint("Server", "PORT", fallback=8443)
        self.ssl_cert: str = self.config.get("SSL", "CERT_FILE", fallback="cert.pem")
        self.ssl_key: str = self.config.get("SSL", "KEY_FILE", fallback="key.pem")