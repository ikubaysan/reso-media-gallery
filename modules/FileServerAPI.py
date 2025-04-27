import os
from typing import Optional
from urllib.parse import unquote

from flask import Flask, request, send_from_directory
from modules.FileServer import FileServer

import logging

logger = logging.getLogger(__name__)

class FileServerAPI:
    def __init__(self, file_server: FileServer, host: str = "0.0.0.0", port: int = 5000, ssl_context: Optional[tuple]=None, public_url: Optional[str] = None):
        self.file_server = file_server
        self.host = host
        self.port = port
        self.public_url = public_url if public_url else f"http://{self.host}:{self.port}"
        self.app = Flask(__name__)
        self.ssl_context = ssl_context

        # Serve files from the root directory
        @self.app.route('/files/<path:filepath>', methods=['GET'])
        def serve_file(filepath):
            """
            Serves files from /files/.
            Example: http://localhost:5000/files/root/folder/image.jpg?session_id=123
            """
            session_id = request.args.get("session_id")  # Doesn't affect functionality
            return self.serve_static_file(filepath, base_path=self.file_server.media_root_dir)

        @self.app.route('/thumbs/<path:filepath>', methods=['GET'])
        def serve_thumbnail(filepath):
            """
            Serves or generates thumbnails dynamically.
            Example: http://localhost:5000/thumbs/root/folder/image.jpg?session_id=123
            """
            session_id = request.args.get("session_id")  # Doesn't affect functionality
            return self.serve_or_generate_thumbnail(filepath)

        # This should be a GET endpoint, but we have to use POST because
        # Resonite can't send a body with a GET request.pp
        # Example with session id and sorting: http://localhost:5000/get-files?sort_by=name&session_id=123
        @self.app.route('/get-files', methods=['POST'])
        def get_files():
            """Returns a pipe-separated string with file and folder info."""
            logger.info(f"Received request to get files in subfolder: {request.data.decode('utf-8').strip()}")
            try:
                subfolder = request.data.decode('utf-8').strip()
                sort_by = request.args.get("sort_by")

                if not subfolder:
                    logger.info("No subfolder name defined, using root directory.")

                if not sort_by:
                    logger.info("No sort_by parameter defined, sorting by name.")
                    sort_by = "name"

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
        original_file_path = os.path.abspath(os.path.join(self.file_server.media_root_dir, filepath))

        # Security check to prevent directory traversal attacks
        if not original_file_path.startswith(self.file_server.media_root_dir):
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
        self.app.run(host=self.host, port=self.port, ssl_context=self.ssl_context, threaded=True)
