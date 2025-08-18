"""Database migrations for Ponderous schema setup."""

from ponderous.infrastructure.database.connection import DatabaseConnection
from ponderous.shared.exceptions import DatabaseError


class DatabaseMigrator:
    """Handles database schema migrations and setup."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """Initialize migrator with database connection.

        Args:
            db_connection: Database connection manager
        """
        self.db = db_connection

    def initialize_database(self) -> None:
        """Initialize database with complete schema."""
        try:
            self._create_migration_table()
            self._run_all_migrations()
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {e}") from e

    def _create_migration_table(self) -> None:
        """Create migration tracking table."""
        query = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """
        self.db.execute_query(query)

    def _run_all_migrations(self) -> None:
        """Run all pending migrations."""
        migrations = self._get_migrations()
        applied_versions = self._get_applied_migrations()

        for version, description, sql in migrations:
            if version not in applied_versions:
                self._run_migration(version, description, sql)

    def _get_applied_migrations(self) -> set:
        """Get set of applied migration versions."""
        if not self.db.table_exists("schema_migrations"):
            return set()

        query = "SELECT version FROM schema_migrations"
        results = self.db.fetch_all(query)
        return {row[0] for row in results}

    def _run_migration(self, version: int, description: str, sql: str) -> None:
        """Run a single migration.

        Args:
            version: Migration version number
            description: Migration description
            sql: SQL commands to execute
        """
        try:
            with self.db.transaction() as conn:
                # Execute migration SQL
                for statement in sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        conn.execute(statement)

                # Record migration as applied
                conn.execute(
                    "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                    (version, description),
                )

        except Exception as e:
            raise DatabaseError(f"Migration {version} failed: {e}") from e

    def _get_migrations(self) -> list[tuple]:
        """Get list of all migrations (version, description, sql).

        Returns:
            List of migration tuples: (version, description, sql)
        """
        return [
            (1, "Create users table", self._migration_001_users()),
            (
                2,
                "Create collection sources table",
                self._migration_002_collection_sources(),
            ),
            (
                3,
                "Create user collections table",
                self._migration_003_user_collections(),
            ),
            (4, "Create commanders table", self._migration_004_commanders()),
            (5, "Create deck statistics table", self._migration_005_deck_statistics()),
            (
                6,
                "Create deck card inclusions table",
                self._migration_006_deck_card_inclusions(),
            ),
            (7, "Create indexes for performance", self._migration_007_indexes()),
        ]

    def _migration_001_users(self) -> str:
        """Migration 001: Create users table."""
        return """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_sync TIMESTAMP,
                total_cards INTEGER DEFAULT 0,
                total_value REAL DEFAULT 0.0
            )
        """

    def _migration_002_collection_sources(self) -> str:
        """Migration 002: Create collection sources table."""
        return """
            CREATE TABLE collection_sources (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                api_endpoint TEXT,
                requires_auth BOOLEAN DEFAULT FALSE,
                rate_limit_per_second REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Insert default sources
            INSERT INTO collection_sources (source_id, source_name, api_endpoint, rate_limit_per_second)
            VALUES
                ('moxfield', 'Moxfield', 'https://api2.moxfield.com/v2', 2.0),
                ('archidekt', 'Archidekt', 'https://archidekt.com/api', 1.0)
        """

    def _migration_003_user_collections(self) -> str:
        """Migration 003: Create user collections table."""
        return """
            CREATE TABLE user_collections (
                user_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                card_id TEXT NOT NULL,
                card_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                foil_quantity INTEGER DEFAULT 0,
                price_usd REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, source_id, card_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (source_id) REFERENCES collection_sources(source_id)
            )
        """

    def _migration_004_commanders(self) -> str:
        """Migration 004: Create commanders table."""
        return """
            CREATE TABLE commanders (
                commander_name TEXT PRIMARY KEY,
                card_id TEXT,
                color_identity TEXT, -- JSON array
                total_decks INTEGER DEFAULT 0,
                popularity_rank INTEGER,
                avg_deck_price REAL DEFAULT 0.0,
                salt_score REAL DEFAULT 0.0,
                power_level REAL DEFAULT 5.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

    def _migration_005_deck_statistics(self) -> str:
        """Migration 005: Create deck statistics table."""
        return """
            CREATE TABLE deck_statistics (
                stat_id TEXT PRIMARY KEY,
                commander_name TEXT NOT NULL,
                archetype_id TEXT,
                theme_id TEXT,
                budget_range TEXT,
                total_decks INTEGER DEFAULT 0,
                avg_price REAL DEFAULT 0.0,
                win_rate REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (commander_name) REFERENCES commanders(commander_name)
            )
        """

    def _migration_006_deck_card_inclusions(self) -> str:
        """Migration 006: Create deck card inclusions table."""
        return """
            CREATE TABLE deck_card_inclusions (
                commander_name TEXT NOT NULL,
                archetype_id TEXT,
                budget_range TEXT,
                card_name TEXT NOT NULL,
                card_id TEXT,
                inclusion_rate REAL NOT NULL,
                synergy_score REAL DEFAULT 0.0,
                category TEXT DEFAULT 'staple',
                price_usd REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (commander_name, archetype_id, budget_range, card_name),
                FOREIGN KEY (commander_name) REFERENCES commanders(commander_name)
            )
        """

    def _migration_007_indexes(self) -> str:
        """Migration 007: Create performance indexes."""
        return """
            -- User collections indexes
            CREATE INDEX idx_user_collections_user_id ON user_collections(user_id);
            CREATE INDEX idx_user_collections_card_name ON user_collections(card_name);
            CREATE INDEX idx_user_collections_source ON user_collections(source_id);

            -- Commander indexes
            CREATE INDEX idx_commanders_popularity ON commanders(popularity_rank);
            CREATE INDEX idx_commanders_color_identity ON commanders(color_identity);
            CREATE INDEX idx_commanders_power_level ON commanders(power_level);

            -- Deck statistics indexes
            CREATE INDEX idx_deck_stats_commander ON deck_statistics(commander_name);
            CREATE INDEX idx_deck_stats_archetype ON deck_statistics(archetype_id);
            CREATE INDEX idx_deck_stats_budget ON deck_statistics(budget_range);

            -- Deck card inclusions indexes
            CREATE INDEX idx_deck_inclusions_commander ON deck_card_inclusions(commander_name);
            CREATE INDEX idx_deck_inclusions_card ON deck_card_inclusions(card_name);
            CREATE INDEX idx_deck_inclusions_inclusion_rate ON deck_card_inclusions(inclusion_rate);
            CREATE INDEX idx_deck_inclusions_category ON deck_card_inclusions(category)
        """

    def reset_database(self) -> None:
        """Reset database by dropping all tables."""
        tables = [
            "deck_card_inclusions",
            "deck_statistics",
            "commanders",
            "user_collections",
            "collection_sources",
            "users",
            "schema_migrations",
        ]

        for table in tables:
            if self.db.table_exists(table):
                self.db.execute_query(f"DROP TABLE {table}")

    def get_database_info(self) -> dict:
        """Get database information and statistics.

        Returns:
            Dictionary with database information
        """
        info = {
            "tables": [],
            "migrations_applied": 0,
            "total_users": 0,
            "total_collections": 0,
            "total_commanders": 0,
        }

        # Get table information
        tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
        """
        tables = self.db.fetch_all(tables_query)
        info["tables"] = [row[0] for row in tables]

        # Get migration count
        if self.db.table_exists("schema_migrations"):
            migration_count = self.db.fetch_one(
                "SELECT COUNT(*) FROM schema_migrations"
            )
            info["migrations_applied"] = migration_count[0] if migration_count else 0

        # Get user count
        if self.db.table_exists("users"):
            user_count = self.db.fetch_one("SELECT COUNT(*) FROM users")
            info["total_users"] = user_count[0] if user_count else 0

        # Get collection count
        if self.db.table_exists("user_collections"):
            collection_count = self.db.fetch_one(
                "SELECT COUNT(DISTINCT user_id) FROM user_collections"
            )
            info["total_collections"] = collection_count[0] if collection_count else 0

        # Get commander count
        if self.db.table_exists("commanders"):
            commander_count = self.db.fetch_one("SELECT COUNT(*) FROM commanders")
            info["total_commanders"] = commander_count[0] if commander_count else 0

        return info
