import sqlite3
import uuid
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ThumbnailDatabase:
    """Handles storing and retrieving thumbnail mappings using SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self):
        """Create necessary database tables if they don't exist."""
        logger.info(f"Initializing database at {self.db_path}")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create the thumbnails table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS thumbnails (
                    original_path TEXT PRIMARY KEY,
                    thumbnail_guid TEXT UNIQUE
                )
            """)

            # Create metadata table to store database GUID
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    db_guid TEXT UNIQUE NOT NULL
                )
            """)

            # Ensure the metadata table contains a GUID
            cursor.execute("SELECT db_guid FROM metadata WHERE id = 1")
            result = cursor.fetchone()

            if not result:
                db_guid = str(uuid.uuid4())  # Generate new GUID for the database
                cursor.execute("INSERT INTO metadata (id, db_guid) VALUES (1, ?)", (db_guid,))
                conn.commit()

    def get_database_guid(self) -> str:
        """Retrieve the GUID of the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT db_guid FROM metadata WHERE id = 1")
            result = cursor.fetchone()
            return result[0] if result else "UNKNOWN"

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
