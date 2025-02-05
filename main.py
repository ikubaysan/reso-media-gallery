import os
import sys
import logging
from flask import Flask, request, jsonify
from typing import List, Optional, Dict


# Configure logging
def configure_console_logger(level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


configure_console_logger()
logger = logging.getLogger(__name__)


class FileServer:
    def __init__(
        self,
        root_dir: str,
        allowed_extensions: Optional[List[str]] = None,
        blacklisted_subfolders: Optional[List[str]] = None,
    ):
        self.root_dir = os.path.abspath(root_dir)
        self.allowed_extensions = allowed_extensions or [
            ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi", ".mkv"
        ]
        self.blacklisted_subfolders = set(blacklisted_subfolders or [])

        if not os.path.exists(self.root_dir):
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        logger.info(f"FileServer initialized with root directory: {self.root_dir}")

    def is_blacklisted(self, subfolder: str) -> bool:
        """Checks if any part of the requested subfolder is blacklisted."""
        parts = os.path.normpath(subfolder).split(os.sep)
        for part in parts:
            if part in self.blacklisted_subfolders:
                logger.warning(f"Access denied: Requested subfolder contains blacklisted name '{part}'")
                return True
        return False

    def get_files_and_subfolders_in_subfolder(self, subfolder: str, sort_by: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Returns both the list of eligible files and the list of subfolder names in the requested subfolder.
        Supports sorting files by name or modified date.
        """
        full_dir_path = os.path.abspath(os.path.join(self.root_dir, subfolder))
        logger.info(f"Requested subfolder: {full_dir_path}")

        # Security check: Prevent directory traversal attacks
        if not full_dir_path.startswith(self.root_dir):
            raise ValueError(f"Attempted directory traversal attack with path: {subfolder}")

        if self.is_blacklisted(subfolder):
            return {"files": [], "subfolders": []}  # Block access and log it

        if not os.path.isdir(full_dir_path):
            raise ValueError(f"Requested subfolder does not exist: {full_dir_path}")

        # Get list of eligible files
        files = [
            f for f in os.listdir(full_dir_path)
            if os.path.isfile(os.path.join(full_dir_path, f)) and os.path.splitext(f)[1].lower() in self.allowed_extensions
        ]

        # Get list of subfolders
        subfolders = [
            d for d in os.listdir(full_dir_path)
            if os.path.isdir(os.path.join(full_dir_path, d))
        ]

        # Apply sorting if requested
        if sort_by == "name":
            files.sort()
        elif sort_by == "date":
            files.sort(key=lambda x: os.path.getmtime(os.path.join(full_dir_path, x)), reverse=True)

        logger.info(f"Returning {len(files)} files and {len(subfolders)} subfolders from {subfolder}")
        return {"files": files, "subfolders": subfolders}


class FileServerAPI:
    def __init__(self, file_server: FileServer, host: str = "0.0.0.0", port: int = 5000):
        self.file_server = file_server
        self.host = host
        self.port = port
        self.app = Flask(__name__)

        # Example
        # Endpoint: http://<host>:<port>/get-files?sort_by=name
        # Body:     Subfolder name (e.g., "images/cat_pics")
        @self.app.route('/get-files', methods=['GET'])
        def get_files():
            try:
                subfolder = request.data.decode('utf-8').strip()  # Read plain text from body
                sort_by = request.args.get("sort_by")  # Optional sorting param ("name" or "date")

                if not subfolder:
                    logger.info("No subfolder name was defined in GET request body, using root directory.")

                result = self.file_server.get_files_and_subfolders_in_subfolder(subfolder, sort_by)

                return jsonify(result)

            except ValueError as e:
                logger.warning(f"Bad request: {e}")
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error(f"Internal error: {e}")
                return jsonify({"error": "Internal Server Error"}), 500

    def run(self):
        logger.info(f"Starting FileServerAPI on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port)


if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    blacklisted_folders = ["ignore", "private"]  # Define blacklisted subfolder names

    server = FileServer(root_directory, blacklisted_subfolders=blacklisted_folders)
    api = FileServerAPI(server, host="0.0.0.0", port=6901)
    api.run()
