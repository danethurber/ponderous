"""Unit tests for database infrastructure."""

import pytest
from unittest.mock import Mock, patch

from ponderous.infrastructure.database.connection import DatabaseConnection
from ponderous.infrastructure.database.migrations import DatabaseMigrator
from ponderous.shared.config import DatabaseConfig, PonderousConfig
from ponderous.shared.exceptions import DatabaseError


class TestDatabaseConnection:
    """Test suite for DatabaseConnection."""

    def test_database_connection_creation_with_memory_config(self):
        """Should create in-memory database connection for testing."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        with db.get_connection() as conn:
            # Test basic functionality
            result = conn.execute("SELECT 1 as test").fetchone()
            assert result[0] == 1

    def test_database_connection_table_exists_check(self):
        """Should correctly check if table exists."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        # Table should not exist initially
        assert db.table_exists("test_table") is False

        # Create table and check again
        db.execute_query("CREATE TABLE test_table (id INTEGER)")
        assert db.table_exists("test_table") is True

    def test_database_connection_fetch_one(self):
        """Should fetch single result correctly."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query("CREATE TABLE test (id INTEGER, name TEXT)")
        db.execute_query("INSERT INTO test VALUES (1, 'test')")

        result = db.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert result == (1, "test")

    def test_database_connection_fetch_all(self):
        """Should fetch multiple results correctly."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query("CREATE TABLE test (id INTEGER)")
        db.execute_query("INSERT INTO test VALUES (1), (2), (3)")

        results = db.fetch_all("SELECT * FROM test ORDER BY id")
        assert results == [(1,), (2,), (3,)]

    def test_database_connection_transaction_success(self):
        """Should commit transaction on success."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query("CREATE TABLE test (id INTEGER)")

        with db.transaction() as conn:
            conn.execute("INSERT INTO test VALUES (1)")
            conn.execute("INSERT INTO test VALUES (2)")

        results = db.fetch_all("SELECT * FROM test ORDER BY id")
        assert results == [(1,), (2,)]

    def test_database_connection_transaction_rollback_on_error(self):
        """Should rollback transaction on error."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query("CREATE TABLE test (id INTEGER PRIMARY KEY)")

        with pytest.raises(DatabaseError):
            with db.transaction() as conn:
                conn.execute("INSERT INTO test VALUES (1)")
                # This should cause an error (duplicate primary key)
                conn.execute("INSERT INTO test VALUES (1)")

        # Check that no data was committed
        results = db.fetch_all("SELECT * FROM test")
        assert results == []

    def test_database_connection_execute_many(self):
        """Should execute batch operations correctly."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query("CREATE TABLE test (id INTEGER, name TEXT)")

        parameters_list = [(1, "first"), (2, "second"), (3, "third")]
        db.execute_many("INSERT INTO test VALUES (?, ?)", parameters_list)

        results = db.fetch_all("SELECT * FROM test ORDER BY id")
        assert results == [(1, "first"), (2, "second"), (3, "third")]

    def test_database_connection_get_table_schema(self):
        """Should return table schema information."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        db.execute_query(
            """
            CREATE TABLE test (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL
            )
        """
        )

        schema = db.get_table_schema("test")
        assert len(schema) == 3

        # Check that we have the expected columns
        column_names = [col[0] for col in schema]
        assert "id" in column_names
        assert "name" in column_names
        assert "price" in column_names

    def test_database_connection_close(self):
        """Should close connection properly."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)

        # Use connection to create it
        with db.get_connection():
            pass

        # Close connection
        db.close()
        assert db._connection is None

    def test_database_connection_context_manager(self):
        """Should work as context manager."""
        config = DatabaseConfig(memory=True)

        with DatabaseConnection(config) as db:
            result = db.fetch_one("SELECT 1 as test")
            assert result[0] == 1


class TestDatabaseMigrator:
    """Test suite for DatabaseMigrator."""

    def test_database_migrator_initialization(self):
        """Should initialize database with all migrations."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        # Initialize database
        migrator.initialize_database()

        # Check that migration table exists
        assert db.table_exists("schema_migrations")

        # Check that main tables exist
        expected_tables = [
            "users",
            "collection_sources",
            "user_collections",
            "commanders",
            "deck_statistics",
            "deck_card_inclusions",
        ]

        for table in expected_tables:
            assert db.table_exists(table), f"Table {table} should exist"

    def test_database_migrator_applied_migrations_tracking(self):
        """Should track applied migrations correctly."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        migrator.initialize_database()

        # Check migration records
        migrations = db.fetch_all(
            "SELECT version, description FROM schema_migrations ORDER BY version"
        )
        assert len(migrations) == 7  # We have 7 migrations

        # Check first migration
        assert migrations[0][0] == 1
        assert "users table" in migrations[0][1]

    def test_database_migrator_default_collection_sources(self):
        """Should insert default collection sources."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        migrator.initialize_database()

        # Check default sources
        sources = db.fetch_all("SELECT source_id, source_name FROM collection_sources")
        source_ids = [row[0] for row in sources]

        assert "moxfield" in source_ids
        assert "archidekt" in source_ids

    def test_database_migrator_get_database_info(self):
        """Should return database information."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        migrator.initialize_database()

        info = migrator.get_database_info()

        assert "tables" in info
        assert "migrations_applied" in info
        assert info["migrations_applied"] == 7
        assert len(info["tables"]) >= 6  # At least our main tables

    def test_database_migrator_reset_database(self):
        """Should reset database by dropping all tables."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        # Initialize and then reset
        migrator.initialize_database()
        assert db.table_exists("users")

        migrator.reset_database()
        assert not db.table_exists("users")
        assert not db.table_exists("schema_migrations")

    def test_database_migrator_idempotent_initialization(self):
        """Should be safe to run initialization multiple times."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        # Run initialization twice
        migrator.initialize_database()
        migrator.initialize_database()

        # Should still have correct number of migrations
        info = migrator.get_database_info()
        assert info["migrations_applied"] == 7

    def test_database_migrator_handles_migration_errors(self):
        """Should handle migration errors gracefully."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        # Mock a migration to fail
        original_get_migrations = migrator._get_migrations

        def mock_get_migrations():
            migrations = original_get_migrations()
            # Add a bad migration
            migrations.append((999, "Bad migration", "INVALID SQL SYNTAX"))
            return migrations

        migrator._get_migrations = mock_get_migrations

        with pytest.raises(DatabaseError, match="Migration 999 failed"):
            migrator.initialize_database()

    def test_database_migration_sql_syntax(self):
        """Should have valid SQL syntax in all migrations."""
        config = DatabaseConfig(memory=True)
        db = DatabaseConnection(config)
        migrator = DatabaseMigrator(db)

        # Test migrations in order (they have dependencies)
        migrator._create_migration_table()
        migrations = migrator._get_migrations()

        for version, description, sql in migrations:
            # This should not raise an exception
            migrator._run_migration(version, description, sql)
