import os
import sys
import logging
import sqlite3
import uuid

from PIL import Image
from flask import Flask, request, send_from_directory
import mimetypes
from typing import List, Optional
from urllib.parse import quote, unquote


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



class ThumbnailDatabase:
    """Handles storing and retrieving thumbnail mappings using SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """Create the database table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS thumbnails (
                    original_path TEXT PRIMARY KEY,
                    thumbnail_guid TEXT UNIQUE
                )
            """)
            conn.commit()

    def get_thumbnail_guid(self, original_path: str) -> Optional[str]:
        """Retrieve the GUID filename for a given original file, if it exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT thumbnail_guid FROM thumbnails WHERE original_path = ?", (original_path,))
            result = cursor.fetchone()
            return result[0] if result else None

    def store_thumbnail_guid(self, original_path: str, thumbnail_guid: str):
        """Save a new GUID-based thumbnail mapping."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO thumbnails (original_path, thumbnail_guid) VALUES (?, ?)",
                           (original_path, thumbnail_guid))
            conn.commit()


class FileServer:
    def __init__(
        self,
        root_dir: str,
        allowed_extensions: Optional[List[str]] = None,
        blacklisted_subfolders: Optional[List[str]] = None,
    ):

        self.root_dir = os.path.abspath(root_dir)
        self.db = ThumbnailDatabase(DB_PATH)
        self.thumbnail_dir = os.path.join(self.root_dir, THUMBNAIL_DIR)
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None  # Allow all if empty
        self.blacklisted_subfolders = set(blacklisted_subfolders or [])

        if not os.path.exists(self.root_dir):
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        logger.info(f"FileServer initialized with root directory: {self.root_dir}")
        if self.allowed_extensions:
            logger.info(f"Allowed Extensions: {', '.join(self.allowed_extensions)}")
        else:
            logger.info("All file extensions are allowed.")



    def get_thumbnail_path(self, guid: str) -> str:
        """Generates a unique thumbnail path based on the GUID."""
        return os.path.join(THUMBNAIL_DIR, f"{guid}.jpg")

    def generate_thumbnail(self, filepath: str) -> Optional[str]:
        """Generate and save a thumbnail for an image file, storing the path in the database."""
        # Check if we already have a GUID mapping for this file
        thumbnail_guid = self.db.get_thumbnail_guid(filepath)

        if not thumbnail_guid:
            thumbnail_guid = str(uuid.uuid4())  # Generate new GUID
            self.db.store_thumbnail_guid(filepath, thumbnail_guid)

        thumbnail_path = self.get_thumbnail_path(thumbnail_guid)

        # Check if the file already exists before regenerating
        if os.path.exists(thumbnail_path):
            return thumbnail_path

        try:
            with Image.open(filepath) as img:
                img.thumbnail(THUMBNAIL_SIZE)
                img.save(thumbnail_path, format="JPEG")
                logger.info(f"Thumbnail generated: {thumbnail_path}")

            return thumbnail_path
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {filepath}: {e}")
            return None


    def is_blacklisted(self, subfolder: str) -> bool:
        """Checks if any part of the requested subfolder is blacklisted."""
        parts = os.path.normpath(subfolder).split(os.sep)
        for part in parts:
            if part in self.blacklisted_subfolders:
                logger.warning(f"Access denied: Requested subfolder contains blacklisted name '{part}'")
                return True
        return False

    def format_string(self, value: str) -> str:
        """Ensures the string is exactly 260 characters, including the separator '|'."""
        max_content_length = MAX_LENGTH - 1  # Reserve space for '|'
        formatted_value = f"{value:<{max_content_length}}"[:max_content_length]  # Ensure length
        return formatted_value + "|"  # Append '|' to the end

    def get_files_and_subfolders_in_subfolder(
        self, subfolder: str, base_url: str, sort_by: Optional[str] = None
    ) -> str:
        """
        Returns a string where each item is exactly 260 characters long:
        <count of media files>|<count of subfolders>|<media file 0>|<media file 1>|...|<subfolder 0>|<subfolder 1>
        """

        original_requested_subfolder = subfolder

        # If subfolder starts with "root/", remove it
        if subfolder.startswith("root/"):
            subfolder = subfolder[4:]

        subfolder = os.path.normpath(subfolder)

        # Replace all \ with /
        subfolder = subfolder.replace("\\", "/")

        # Replace all // with /
        subfolder = subfolder.replace("//", "/")

        # If subfolder starts with a slash, remove it
        if subfolder.startswith("/"):
            subfolder = subfolder[1:]

        # If subfolder ends with a slash, remove it
        if subfolder.endswith("/"):
            subfolder = subfolder[:-1]

        full_dir_path = os.path.abspath(os.path.join(self.root_dir, subfolder))
        logger.info(f"Requested subfolder: {subfolder}, original: {original_requested_subfolder}, full path: {full_dir_path}")

        # Security check: Prevent directory traversal attacks
        if not full_dir_path.startswith(self.root_dir):
            raise ValueError(f"Attempted directory traversal attack with path: {subfolder}")

        if self.is_blacklisted(subfolder):
            return self.format_string("0") + "|" + self.format_string("0")

        if not os.path.isdir(full_dir_path):
            raise ValueError(f"Requested subfolder does not exist: {full_dir_path}")

        # Get list of eligible files (construct full URLs)
        files = []
        for f in os.listdir(full_dir_path):
            file_path = os.path.join(full_dir_path, f)
            if os.path.isfile(file_path):
                ext = os.path.splitext(f)[1].lower()
                if self.allowed_extensions is None or ext in self.allowed_extensions:
                    if subfolder in ["", "."]:
                        files.append(f"{base_url}/files/{quote(f)}")
                    else:
                        files.append(f"{base_url}/files/{subfolder}/{quote(f)}")

        # Get list of subfolders
        subfolders = []

        # Append ".." to subfolders if not in root directory, meaning we need to allow the ability to go up
        if subfolder not in ["", "."]:
            subfolders.append("..")

        for d in os.listdir(full_dir_path):
            if os.path.isdir(os.path.join(full_dir_path, d)):
                subfolders.append(d)

        # Apply sorting if requested
        if sort_by == "name":
            files.sort()
        elif sort_by == "date":
            files_with_dates = [(file, os.path.getmtime(os.path.join(full_dir_path, os.path.basename(file)))) for file in files]
            files_with_dates.sort(key=lambda x: x[1], reverse=True)
            files = [file[0] for file in files_with_dates]

        result = ""

        # Append the normalized subfolder path

        # If subfolder does not start with "root/", add it,
        # and if it starts with /, remove it

        if subfolder.startswith("."):
            subfolder = self.format_string(subfolder[1:])

        if subfolder.startswith("/"):
            subfolder = self.format_string(subfolder[1:])

        if not subfolder.startswith("root/"):
            subfolder = self.format_string("root/" + subfolder)

        normalized_subfolder_path = self.format_string(subfolder)
        result += normalized_subfolder_path

        # Construct the pipe-separated response string
        result += self.format_string(str(len(subfolders))) + self.format_string(str(len(files)))

        for folder in subfolders:
            result += self.format_string(folder)

        for file in files:
            result += self.format_string(file)

        return result


class FileServerAPI:
    def __init__(self, file_server: FileServer, host: str = "0.0.0.0", port: int = 5000, public_url: Optional[str] = None):
        self.file_server = file_server
        self.host = host
        self.port = port
        self.public_url = public_url if public_url else f"http://{self.host}:{self.port}"
        self.app = Flask(__name__)

        # Serve files from the root directory
        @self.app.route('/files/<path:filepath>', methods=['GET'])
        def serve_file(filepath):
            """Serves files from /files/."""
            return self.serve_static_file(filepath, base_path=self.file_server.root_dir)

        @self.app.route('/thumbs/<path:filepath>', methods=['GET'])
        def serve_thumbnail(filepath):
            """Serves or generates thumbnails dynamically."""
            return self.serve_or_generate_thumbnail(filepath)

        # This should be a GET endpoint, but we have to use POST because
        # Resonite can't send a body with a GET request.pp
        @self.app.route('/get-files', methods=['POST'])
        def get_files():
            """Returns a pipe-separated string with file and folder info."""
            try:
                subfolder = request.data.decode('utf-8').strip()
                sort_by = request.args.get("sort_by")

                if not subfolder:
                    logger.info("No subfolder name defined, using root directory.")

                result = self.file_server.get_files_and_subfolders_in_subfolder(subfolder, self.public_url, sort_by)
                return result

            except ValueError as e:
                logger.warning(f"Bad request: {e}")
                return f"Error: {e}", 400
            except Exception as e:
                logger.error(f"Internal error: {e}")
                return "Internal Server Error", 500

    def serve_static_file(self, filepath, base_path):
        """Generic file serving function with security checks."""
        filepath = unquote(filepath)
        full_path = os.path.abspath(os.path.join(base_path, filepath))

        # Security check: Prevent directory traversal attacks
        if not full_path.startswith(base_path):
            logger.warning(f"Security Alert: Attempted access outside root - {filepath}")
            return "Access denied", 403

        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            logger.warning(f"File not found: {full_path}")
            return "File not found", 404

        ext = os.path.splitext(full_path)[1].lower()
        if self.file_server.allowed_extensions is not None and ext not in self.file_server.allowed_extensions:
            logger.warning(f"Forbidden file access: {full_path}")
            return "File type not allowed", 403

        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))

    def serve_or_generate_thumbnail(self, filepath):
        """Serve cached thumbnails or generate them on demand."""
        filepath = unquote(filepath)
        original_file_path = os.path.abspath(os.path.join(self.file_server.root_dir, filepath))

        # Security check to prevent directory traversal attacks
        if not original_file_path.startswith(self.file_server.root_dir):
            logger.warning(f"Security Alert: Attempted access outside root - {filepath}")
            return "Access denied", 403

        if not os.path.exists(original_file_path) or not os.path.isfile(original_file_path):
            logger.warning(f"File not found: {original_file_path}")
            return "File not found", 404

        # Lookup the GUID filename
        thumbnail_guid = self.file_server.db.get_thumbnail_guid(original_file_path)
        if not thumbnail_guid:
            logger.info(f"Thumbnail not found for {filepath}. Generating...")
            self.file_server.generate_thumbnail(original_file_path)
            thumbnail_guid = self.file_server.db.get_thumbnail_guid(original_file_path)

        if not thumbnail_guid:
            return "Thumbnail generation failed", 500

        thumbnail_path = self.file_server.get_thumbnail_path(thumbnail_guid)

        return send_from_directory(os.path.dirname(thumbnail_path), os.path.basename(thumbnail_path))


    def run(self):
        logger.info(f"Starting FileServerAPI on {self.host}:{self.port}")
        #self.app.run(host=self.host, port=self.port, threaded=True)
        self.app.run(host=self.host, port=self.port, ssl_context=('cert.pem', 'key.pem'), threaded=True)


if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    blacklisted_folders = ["ignore", "private"]  # Define blacklisted subfolder names
    public_url = "https://gallery.ikubaysan.com:8443"  # Set your custom domain

    # Empty list means all extensions are allowed
    allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]

    server = FileServer(root_directory, blacklisted_subfolders=blacklisted_folders, allowed_extensions=allowed_extensions)
    api = FileServerAPI(server, host="0.0.0.0", port=8443, public_url=public_url)
    api.run()
