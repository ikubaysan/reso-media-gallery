import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory
from typing import List, Optional, Dict
from urllib.parse import quote, unquote


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
        self.allowed_extensions = set(allowed_extensions or [
            ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi", ".mkv"
        ])
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

    def get_files_and_subfolders_in_subfolder(
            self, subfolder: str, base_url: str, sort_by: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Returns both the list of full file URLs and the list of subfolder names in the requested subfolder.
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

        # Get list of eligible files (construct full URLs)
        files = [
            quote(f) for f in os.listdir(full_dir_path)
            if
            os.path.isfile(os.path.join(full_dir_path, f)) and os.path.splitext(f)[1].lower() in self.allowed_extensions
        ]

        # Convert filenames into full URLs
        file_urls = [f"{base_url}/{subfolder}/{file}" for file in files]

        # Get list of subfolders
        subfolders = [
            d for d in os.listdir(full_dir_path)
            if os.path.isdir(os.path.join(full_dir_path, d))
        ]

        # Apply sorting if requested
        if sort_by == "name":
            file_urls.sort()
        elif sort_by == "date":
            files_with_dates = [(file, os.path.getmtime(os.path.join(full_dir_path, file))) for file in files]
            files_with_dates.sort(key=lambda x: x[1], reverse=True)
            file_urls = [f"{base_url}/{subfolder}/{quote(file[0])}" for file in files_with_dates]

        logger.info(f"Returning {len(file_urls)} files and {len(subfolders)} subfolders from {subfolder}")
        return {"files": file_urls, "subfolders": subfolders}


class FileServerAPI:
    def __init__(self, file_server: FileServer, host: str = "0.0.0.0", port: int = 5000):
        self.file_server = file_server
        self.host = host
        self.port = port
        self.app = Flask(__name__)

        # Base URL for file access
        self.base_url = f"http://{self.host}:{self.port}/files"

        # Serve files from the root directory
        @self.app.route('/files/<path:filepath>', methods=['GET'])
        def serve_file(filepath):
            """Serves files ensuring only allowed extensions are accessible."""

            # Decode URL-encoded characters (e.g., spaces, special characters)
            filepath = unquote(filepath)

            # Compute full path
            full_path = os.path.abspath(os.path.join(self.file_server.root_dir, filepath))

            # Security: Ensure the file is within the allowed root directory
            if not full_path.startswith(self.file_server.root_dir):
                logger.warning(f"Security Alert: Attempted access outside root - {filepath}")
                return jsonify({"error": "Access denied"}), 403

            # Ensure file exists
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                logger.warning(f"File not found: {full_path}")
                return jsonify({"error": "File not found"}), 404

            # Ensure file extension is allowed
            ext = os.path.splitext(full_path)[1].lower()
            if ext not in self.file_server.allowed_extensions:
                logger.warning(f"Forbidden file access: {full_path}")
                return jsonify({"error": "File type not allowed"}), 403

            # Get the directory and file name separately
            directory, filename = os.path.split(full_path)

            # Serve file correctly
            return send_from_directory(directory, filename)

        @self.app.route('/get-files', methods=['GET'])
        def get_files():
            """Returns a list of full URLs to the files in the requested subfolder."""
            try:
                subfolder = request.data.decode('utf-8').strip()
                sort_by = request.args.get("sort_by")

                if not subfolder:
                    logger.info("No subfolder name defined, using root directory.")

                result = self.file_server.get_files_and_subfolders_in_subfolder(subfolder, self.base_url, sort_by)
                return jsonify(result)

            except ValueError as e:
                logger.warning(f"Bad request: {e}")
                return jsonify({"error": str(e)}), 400
            except Exception as e:
                logger.error(f"Internal error: {e}")
                return jsonify({"error": "Internal Server Error"}), 500

    def run(self):
        logger.info(f"Starting FileServerAPI on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, threaded=True)


if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    blacklisted_folders = ["ignore", "private"]  # Define blacklisted subfolder names

    server = FileServer(root_directory, blacklisted_subfolders=blacklisted_folders)
    api = FileServerAPI(server, host="localhost", port=6901)
    api.run()
