import os
import uuid
from typing import Optional, List, Tuple
from urllib.parse import quote
from PIL import Image
from modules.ThumbnailDatabase import ThumbnailDatabase
import logging

logger = logging.getLogger(__name__)

class FileServer:
    def __init__(
        self,
        db_path: str,
        thumbnail_dir: str,
        thumbnail_size: Tuple[int, int],
        max_response_part_length: int,
        media_root_dir: str,
        allowed_extensions: Optional[List[str]] = None,
        blacklisted_subfolders: Optional[List[str]] = None,
    ):

        # Log all of the parameters
        logger.info(f"db_path: {db_path}\nthumbnail_dir: {thumbnail_dir}\nthumbnail_size: {thumbnail_size}\n"
                    f"max_response_part_length: {max_response_part_length}\n"
                    f"media_root_dir: {media_root_dir}\nallowed_extensions: {allowed_extensions}\n"
                    f"blacklisted_subfolders: {blacklisted_subfolders}")

        self.media_root_dir = os.path.abspath(media_root_dir)
        self.db = ThumbnailDatabase(db_path)
        self.thumbnail_size = thumbnail_size
        self.max_response_part_length = max_response_part_length
        self.thumbnail_dir = thumbnail_dir
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None  # Allow all if empty
        self.blacklisted_subfolders = set(blacklisted_subfolders or [])

        if not os.path.exists(self.media_root_dir):
            raise ValueError(f"Root directory does not exist: {self.media_root_dir}")

        logger.info(f"FileServer initialized with root directory: {self.media_root_dir}")
        if self.allowed_extensions:
            logger.info(f"Allowed Extensions: {', '.join(self.allowed_extensions)}")
        else:
            logger.info("All file extensions are allowed.")



    def get_thumbnail_path(self, guid: str) -> str:
        """Generates a unique thumbnail path based on the GUID."""
        return os.path.join(self.thumbnail_dir, f"{guid}.jpg")

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
                # Convert to RGB if the image is in 'P' or 'RGBA' mode
                if img.mode in ("P", "RGBA"):
                    img = img.convert("RGB")

                img.thumbnail(self.thumbnail_size)
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
        max_content_length = self.max_response_part_length - 1  # Reserve space for '|'
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

        full_dir_path = os.path.abspath(os.path.join(self.media_root_dir, subfolder))
        logger.info(f"Requested subfolder: {subfolder}, original: {original_requested_subfolder}, full path: {full_dir_path}")

        # Security check: Prevent directory traversal attacks
        if not full_dir_path.startswith(self.media_root_dir):
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

        db_guid = self.db.get_database_guid()

        result += self.format_string(db_guid)  # Append the database GUID

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
        result += self.format_string(str(len(subfolders)))
        result += self.format_string(str(len(files)))

        for folder in subfolders:
            result += self.format_string(folder)

        for file in files:
            result += self.format_string(file)

        return result
