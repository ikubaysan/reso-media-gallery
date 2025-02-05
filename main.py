import os
import sys
import logging
from flask import Flask, request, jsonify
from typing import List, Optional


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
    def __init__(self, root_dir: str, allowed_extensions: Optional[List[str]] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.allowed_extensions = allowed_extensions or [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mov", ".avi",
                                                         ".mkv"]

        if not os.path.exists(self.root_dir):
            raise ValueError(f"Root directory does not exist: {self.root_dir}")

        logger.info(f"FileServer initialized with root directory: {self.root_dir}")

    def get_files_in_subfolder(self, subfolder: str) -> List[str]:
        normalized_path = os.path.abspath(os.path.join(self.root_dir, subfolder))
        logger.info(f"Requested subfolder: {subfolder}")

        if not normalized_path.startswith(self.root_dir):
            logger.warning(f"Attempted directory traversal attack with path: {subfolder}")
            return []

        if not os.path.isdir(normalized_path):
            logger.warning(f"Requested subfolder does not exist: {normalized_path}")
            return []

        files = [
            f for f in os.listdir(normalized_path)
            if os.path.isfile(os.path.join(normalized_path, f)) and os.path.splitext(f)[
                1].lower() in self.allowed_extensions
        ]

        logger.info(f"Returning {len(files)} files from subfolder: {subfolder}")
        return files


class FileServerAPI:
    def __init__(self, file_server: FileServer, host: str = "0.0.0.0", port: int = 5000):
        self.file_server = file_server
        self.host = host
        self.port = port
        self.app = Flask(__name__)

        @self.app.route('/get-files', methods=['GET'])
        def get_files():
            try:
                subfolder = request.data.decode('utf-8').strip()  # Read plain text from body

                if not subfolder:
                    logger.warning("Invalid request body: missing subfolder name")
                    return jsonify({"error": "Missing subfolder name in request body"}), 400

                files = self.file_server.get_files_in_subfolder(subfolder)
                return jsonify({"files": files})

            except Exception as e:
                logger.error(f"Error processing request: {e}")
                return jsonify({"error": "Internal Server Error"}), 500

    def run(self):
        logger.info(f"Starting FileServerAPI on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port)


if __name__ == "__main__":
    root_directory = r"C:\Users\PC\Pictures"  # Change this to your desired directory
    server = FileServer(root_directory)
    api = FileServerAPI(server, host="0.0.0.0", port=6901)
    api.run()
