import os
import sys
import logging
from flask import Flask, request, send_from_directory
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


configure_console_logger()
logger = logging.getLogger(__name__)

MAX_LENGTH = 260  # Fixed length for each part of the response


class FileServer:
    def __init__(
        self,
        root_dir: str,
        allowed_extensions: Optional[List[str]] = None,
        blacklisted_subfolders: Optional[List[str]] = None,
    ):
        self.root_dir = os.path.abspath(root_dir)
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None  # Allow all if empty
        self.blacklisted_subfolders = set(blacklisted_subfolders or [])

        if not os.path.exists(self.root_dir):
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        logger.info(f"FileServer initialized with root directory: {self.root_dir}")
        if self.allowed_extensions:
            logger.info(f"Allowed Extensions: {', '.join(self.allowed_extensions)}")
        else:
            logger.info("All file extensions are allowed.")

    def is_blacklisted(self, subfolder: str) -> bool:
        """Checks if any part of the requested subfolder is blacklisted."""
        parts = os.path.normpath(subfolder).split(os.sep)
        for part in parts:
            if part in self.blacklisted_subfolders:
                logger.warning(f"Access denied: Requested subfolder contains blacklisted name '{part}'")
                return True
        return False

    def format_string(self, value: str) -> str:
        """Pads or truncates a string to exactly 260 characters."""
        return f"{value:<{MAX_LENGTH}}"[:MAX_LENGTH]

    def get_files_and_subfolders_in_subfolder(
        self, subfolder: str, base_url: str, sort_by: Optional[str] = None
    ) -> str:
        """
        Returns a string where each item is exactly 260 characters long:
        <count of media files>|<count of subfolders>|<media file 0>|<media file 1>|...|<subfolder 0>|<subfolder 1>
        """
        full_dir_path = os.path.abspath(os.path.join(self.root_dir, subfolder))
        logger.info(f"Requested subfolder: {full_dir_path}")

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
                    files.append(f"{base_url}/files/{subfolder}/{quote(f)}")

        # Get list of subfolders
        subfolders = []
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

        # Construct the pipe-separated response string
        result = self.format_string(str(len(files))) + "|" + self.format_string(str(len(subfolders)))

        for file in files:
            result += "|" + self.format_string(file)
        for folder in subfolders:
            result += "|" + self.format_string(folder)

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
            """Serves files ensuring only allowed extensions are accessible."""

            # Decode URL-encoded characters (e.g., spaces, special characters)
            filepath = unquote(filepath)

            # Compute full path
            full_path = os.path.abspath(os.path.join(self.file_server.root_dir, filepath))

            # Security: Ensure the file is within the allowed root directory
            if not full_path.startswith(self.file_server.root_dir):
                logger.warning(f"Security Alert: Attempted access outside root - {filepath}")
                return "Access denied", 403

            # Ensure file exists
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                logger.warning(f"File not found: {full_path}")
                return "File not found", 404

            # Ensure file extension is allowed
            ext = os.path.splitext(full_path)[1].lower()
            if self.file_server.allowed_extensions is not None and ext not in self.file_server.allowed_extensions:
                logger.warning(f"Forbidden file access: {full_path}")
                return "File type not allowed", 403

            # Get the directory and file name separately
            directory, filename = os.path.split(full_path)

            # Serve file correctly
            return send_from_directory(directory, filename)

        @self.app.route('/get-files', methods=['GET'])
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

    def run(self):
        logger.info(f"Starting FileServerAPI on {self.host}:{self.port}")
        #self.app.run(host=self.host, port=self.port, threaded=True)
        self.app.run(host=self.host, port=self.port, ssl_context=('cert.pem', 'key.pem'), threaded=True)


if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    blacklisted_folders = ["ignore", "private"]  # Define blacklisted subfolder names
    public_url = "https://gallery.ikubaysan.com:8443"  # Set your custom domain

    allowed_extensions = []  # Empty list means all extensions are allowed

    server = FileServer(root_directory, blacklisted_subfolders=blacklisted_folders, allowed_extensions=allowed_extensions)
    api = FileServerAPI(server, host="0.0.0.0", port=8443, public_url=public_url)
    api.run()
