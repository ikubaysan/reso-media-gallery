import os
import sys
import logging

from modules.FileServer import FileServer
from modules.FileServerAPI import FileServerAPI


# Configure logging
def configure_console_logger(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# Initialize logger
configure_console_logger()
logger = logging.getLogger(__name__)

# Global constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # Directory of this script
THUMBNAIL_DIR = os.path.join(SCRIPT_DIR, "thumbnails")  # Separate thumbnail directory
THUMBNAIL_SIZE = (200, 200)  # Thumbnail dimensions
DB_PATH = os.path.join(SCRIPT_DIR, "thumbnails.db")  # SQLite DB file

# Ensure thumbnail directory exists
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

MAX_LENGTH = 260  # Fixed length for each part of the response

if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    blacklisted_folders = ["ignore", "private"]  # Define blacklisted subfolder names
    public_url = "https://gallery.ikubaysan.com:8443"  # Set your custom domain

    # Empty list means all extensions are allowed
    allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

    server = FileServer(db_path=DB_PATH,
                        blacklisted_subfolders=blacklisted_folders,
                        allowed_extensions=allowed_extensions,
                        root_dir=root_directory,
                        thumbnail_dir=THUMBNAIL_DIR,
                        thumbnail_size=THUMBNAIL_SIZE,
                        max_response_part_length=MAX_LENGTH)

    api = FileServerAPI(server, host="0.0.0.0", port=8443, public_url=public_url, ssl_context=("cert.pem", "key.pem"))
    api.run()
