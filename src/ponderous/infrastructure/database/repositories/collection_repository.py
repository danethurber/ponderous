"""Repository for collection data operations."""

import logging
from datetime import datetime
from typing import Any

from ponderous.infrastructure.database.repositories.base import BaseRepository
from ponderous.shared.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class CollectionEntry:
    """Represents a collection entry from import."""

    def __init__(
        self,
        user_id: str,
        card_name: str,
        set_name: str,
        quantity: int,
        condition: str | None = None,
        language: str | None = None,
        foil: bool = False,
        tags: str | None = None,
        import_source: str = "moxfield_csv",
    ) -> None:
        """Initialize collection entry.

        Args:
            user_id: User identifier
            card_name: Name of the card
            set_name: Name of the set/edition
            quantity: Number of copies owned
            condition: Card condition
            language: Card language
            foil: Whether card is foil
            tags: User tags for the card
            import_source: Source of import data
        """
        self.user_id = user_id
        self.card_name = card_name
        self.set_name = set_name
        self.quantity = quantity
        self.condition = condition
        self.language = language or "English"
        self.foil = foil
        self.tags = tags
        self.import_source = import_source


class ImportSession:
    """Represents an import session for tracking."""

    def __init__(
        self,
        user_id: str,
        file_path: str,
        format: str,
        items_processed: int = 0,
        items_imported: int = 0,
        items_skipped: int = 0,
        success_rate: float = 0.0,
        processing_time_seconds: float = 0.0,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Initialize import session.

        Args:
            user_id: User identifier
            file_path: Path to imported file
            format: Import format
            items_processed: Number of items processed
            items_imported: Number of items imported
            items_skipped: Number of items skipped
            success_rate: Success rate percentage
            processing_time_seconds: Processing time
            errors: List of errors encountered
            warnings: List of warnings encountered
        """
        self.user_id = user_id
        self.file_path = file_path
        self.format = format
        self.items_processed = items_processed
        self.items_imported = items_imported
        self.items_skipped = items_skipped
        self.success_rate = success_rate
        self.processing_time_seconds = processing_time_seconds
        self.errors = errors or []
        self.warnings = warnings or []


class CollectionRepository(BaseRepository):
    """Repository for collection data operations."""

    def create_user_if_not_exists(
        self, user_id: str, username: str | None = None
    ) -> bool:
        """Create user if they don't exist.

        Args:
            user_id: User identifier
            username: Optional username

        Returns:
            True if user was created, False if already existed
        """
        # Check if user exists
        existing_user = self.fetch_one(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        )

        if existing_user:
            return False

        # Create new user
        self.execute_query(
            """
            INSERT INTO users (user_id, username, display_name)
            VALUES (?, ?, ?)
            """,
            (user_id, username or user_id, username or user_id),
        )

        logger.info(f"Created new user: {user_id}")
        return True

    def store_import_session(self, session: ImportSession) -> int:
        """Store import session information.

        Args:
            session: Import session data

        Returns:
            Import session ID
        """
        # First check if we have import_sessions table, if not create it
        if not self.db.table_exists("import_sessions"):
            self._create_import_sessions_table()

        query = """
            INSERT INTO import_sessions (
                id, user_id, file_path, format, items_processed, items_imported,
                items_skipped, success_rate, processing_time_seconds,
                errors, warnings, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert lists to JSON strings for storage
        errors_json = str(session.errors) if session.errors else "[]"
        warnings_json = str(session.warnings) if session.warnings else "[]"

        self.execute_query(
            query,
            (
                session.user_id,
                session.file_path,
                session.format,
                session.items_processed,
                session.items_imported,
                session.items_skipped,
                session.success_rate,
                session.processing_time_seconds,
                errors_json,
                warnings_json,
                datetime.now(),
            ),
        )

        # Return a dummy ID since we don't need the actual ID for our use case
        return 1

    def _create_import_sessions_table(self) -> None:
        """Create import_sessions table if it doesn't exist."""
        query = """
            CREATE TABLE IF NOT EXISTS import_sessions (
                id INTEGER,
                user_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                format TEXT NOT NULL,
                items_processed INTEGER DEFAULT 0,
                items_imported INTEGER DEFAULT 0,
                items_skipped INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                processing_time_seconds REAL DEFAULT 0.0,
                errors TEXT DEFAULT '[]',
                warnings TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        self.execute_query(query)

    def store_collection_entries(
        self, entries: list[CollectionEntry], skip_duplicates: bool = True
    ) -> tuple[int, int]:
        """Store collection entries in database.

        Args:
            entries: List of collection entries to store
            skip_duplicates: Whether to skip duplicate entries

        Returns:
            Tuple of (imported_count, skipped_count)
        """
        if not entries:
            return 0, 0

        imported_count = 0
        skipped_count = 0

        # Process in batches for better performance
        batch_size = 1000
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            batch_imported, batch_skipped = self._store_batch(batch, skip_duplicates)
            imported_count += batch_imported
            skipped_count += batch_skipped

        logger.info(
            f"Stored {imported_count} entries, skipped {skipped_count} duplicates"
        )
        return imported_count, skipped_count

    def _store_batch(
        self, entries: list[CollectionEntry], skip_duplicates: bool
    ) -> tuple[int, int]:
        """Store a batch of collection entries.

        Args:
            entries: Batch of entries to store
            skip_duplicates: Whether to skip duplicates

        Returns:
            Tuple of (imported_count, skipped_count)
        """
        imported_count = 0
        skipped_count = 0

        try:
            with self.db.transaction() as conn:
                for entry in entries:
                    if skip_duplicates and self._entry_exists(entry):
                        skipped_count += 1
                        continue

                    # Insert or update entry
                    if skip_duplicates:
                        # Use INSERT OR IGNORE for duplicates
                        query = """
                            INSERT OR IGNORE INTO user_collections_raw (
                                id, user_id, card_name, set_name, quantity, condition,
                                language, foil, tags, import_source, imported_at
                            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                    else:
                        # Use INSERT OR REPLACE to update duplicates
                        query = """
                            INSERT OR REPLACE INTO user_collections_raw (
                                id, user_id, card_name, set_name, quantity, condition,
                                language, foil, tags, import_source, imported_at
                            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """

                    conn.execute(
                        query,
                        (
                            entry.user_id,
                            entry.card_name,
                            entry.set_name,
                            entry.quantity,
                            entry.condition,
                            entry.language,
                            entry.foil,
                            entry.tags,
                            entry.import_source,
                            datetime.now(),
                        ),
                    )
                    imported_count += 1

        except Exception as e:
            raise DatabaseError(f"Failed to store collection batch: {e}") from e

        return imported_count, skipped_count

    def _entry_exists(self, entry: CollectionEntry) -> bool:
        """Check if a collection entry already exists.

        Args:
            entry: Collection entry to check

        Returns:
            True if entry exists
        """
        # First ensure the raw collections table exists
        if not self.db.table_exists("user_collections_raw"):
            self._create_raw_collections_table()
            return False

        result = self.fetch_one(
            """
            SELECT 1 FROM user_collections_raw
            WHERE user_id = ? AND card_name = ? AND set_name = ?
            LIMIT 1
            """,
            (entry.user_id, entry.card_name, entry.set_name),
        )
        return result is not None

    def _create_raw_collections_table(self) -> None:
        """Create user_collections_raw table for CSV imports."""
        query = """
            CREATE TABLE IF NOT EXISTS user_collections_raw (
                id INTEGER,
                user_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                set_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                condition TEXT,
                language TEXT DEFAULT 'English',
                foil BOOLEAN DEFAULT FALSE,
                tags TEXT,
                import_source TEXT DEFAULT 'moxfield_csv',
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, card_name, set_name)
            )
        """
        self.execute_query(query)

        # Create index for performance
        index_query = """
            CREATE INDEX IF NOT EXISTS idx_user_collections_raw_user_card
            ON user_collections_raw(user_id, card_name)
        """
        self.execute_query(index_query)

    def get_user_collection_summary(self, user_id: str) -> dict[str, Any]:
        """Get summary statistics for a user's collection.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with collection summary
        """
        # Ensure table exists
        if not self.db.table_exists("user_collections_raw"):
            return {
                "user_id": user_id,
                "total_cards": 0,
                "unique_cards": 0,
                "sets_represented": 0,
                "foil_cards": 0,
                "conditions": {},
                "languages": {},
                "last_import": None,
            }

        # Get basic counts
        summary_query = """
            SELECT
                COUNT(*) as total_entries,
                SUM(quantity) as total_cards,
                COUNT(DISTINCT card_name) as unique_cards,
                COUNT(DISTINCT set_name) as sets_represented,
                SUM(CASE WHEN foil = 1 THEN quantity ELSE 0 END) as foil_cards,
                MAX(imported_at) as last_import
            FROM user_collections_raw
            WHERE user_id = ?
        """

        result = self.fetch_one(summary_query, (user_id,))
        if not result:
            return {"user_id": user_id, "total_cards": 0}

        summary = {
            "user_id": user_id,
            "total_entries": result[0],
            "total_cards": result[1] or 0,
            "unique_cards": result[2] or 0,
            "sets_represented": result[3] or 0,
            "foil_cards": result[4] or 0,
            "last_import": result[5],
        }

        # Get condition breakdown
        condition_query = """
            SELECT condition, COUNT(*), SUM(quantity)
            FROM user_collections_raw
            WHERE user_id = ? AND condition IS NOT NULL
            GROUP BY condition
        """
        conditions = self.fetch_all(condition_query, (user_id,))
        summary["conditions"] = {
            cond: {"entries": count, "cards": total}
            for cond, count, total in conditions
        }

        # Get language breakdown
        language_query = """
            SELECT language, COUNT(*), SUM(quantity)
            FROM user_collections_raw
            WHERE user_id = ?
            GROUP BY language
        """
        languages = self.fetch_all(language_query, (user_id,))
        summary["languages"] = {
            lang: {"entries": count, "cards": total} for lang, count, total in languages
        }

        return summary

    def get_collection_by_user(
        self, user_id: str, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get collection entries for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of collection entries
        """
        if not self.db.table_exists("user_collections_raw"):
            return []

        query = """
            SELECT
                card_name, set_name, quantity, condition, language,
                foil, tags, import_source, imported_at
            FROM user_collections_raw
            WHERE user_id = ?
            ORDER BY card_name, set_name
        """

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        results = self.fetch_all(query, (user_id,))

        return [
            {
                "card_name": row[0],
                "set_name": row[1],
                "quantity": row[2],
                "condition": row[3],
                "language": row[4],
                "foil": bool(row[5]),
                "tags": row[6],
                "import_source": row[7],
                "imported_at": row[8],
            }
            for row in results
        ]

    def get_import_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get import history for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of records to return

        Returns:
            List of import history records
        """
        if not self.db.table_exists("import_sessions"):
            return []

        query = """
            SELECT
                id, file_path, format, items_processed, items_imported,
                items_skipped, success_rate, processing_time_seconds,
                errors, warnings, created_at
            FROM import_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """

        results = self.fetch_all(query, (user_id, limit))

        return [
            {
                "id": row[0],
                "file_path": row[1],
                "format": row[2],
                "items_processed": row[3],
                "items_imported": row[4],
                "items_skipped": row[5],
                "success_rate": row[6],
                "processing_time_seconds": row[7],
                "errors": row[8],
                "warnings": row[9],
                "created_at": row[10],
            }
            for row in results
        ]
