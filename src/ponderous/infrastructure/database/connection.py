"""Database connection management for DuckDB."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import duckdb

from ponderous.shared.config import DatabaseConfig, get_config
from ponderous.shared.exceptions import DatabaseError


class DatabaseConnection:
    """Manages DuckDB connections with proper resource handling."""

    def __init__(self, config: DatabaseConfig | None = None) -> None:
        """Initialize database connection manager.

        Args:
            config: Database configuration. Uses global config if None.
        """
        self.config = config or get_config().database
        self._connection: duckdb.DuckDBPyConnection | None = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection

    def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create new database connection with configuration."""
        try:
            if self.config.memory:
                # In-memory database for testing
                conn = duckdb.connect(":memory:")
            else:
                # File-based database
                database_path = str(self.config.path)
                conn = duckdb.connect(
                    database=database_path,
                    read_only=self.config.read_only,
                )

            # Configure connection settings
            conn.execute(f"SET threads TO {self.config.threads}")

            return conn

        except Exception as e:
            raise DatabaseError(f"Failed to create database connection: {e}") from e

    @contextmanager
    def get_connection(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Context manager for database connections."""
        try:
            yield self.connection
        except Exception as e:
            # Log error and re-raise
            raise DatabaseError(f"Database operation failed: {e}") from e

    @contextmanager
    def transaction(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Context manager for database transactions."""
        conn = self.connection
        try:
            conn.execute("BEGIN TRANSACTION")
            yield conn
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            raise DatabaseError(f"Transaction failed: {e}") from e

    def execute_query(self, query: str, parameters: tuple | None = None) -> Any:
        """Execute a query with optional parameters.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Query result

        Raises:
            DatabaseError: If query execution fails
        """
        try:
            with self.get_connection() as conn:
                if parameters:
                    return conn.execute(query, parameters)
                else:
                    return conn.execute(query)
        except Exception as e:
            raise DatabaseError(f"Query execution failed: {e}", query) from e

    def execute_many(self, query: str, parameters_list: list) -> None:
        """Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            parameters_list: List of parameter tuples

        Raises:
            DatabaseError: If query execution fails
        """
        try:
            with self.transaction() as conn:
                for parameters in parameters_list:
                    conn.execute(query, parameters)
        except Exception as e:
            raise DatabaseError(f"Batch query execution failed: {e}", query) from e

    def fetch_one(
        self, query: str, parameters: tuple | None = None
    ) -> tuple[Any, ...] | None:
        """Execute query and fetch one result.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Single result tuple or None
        """
        result = self.execute_query(query, parameters)
        return result.fetchone() if result else None

    def fetch_all(self, query: str, parameters: tuple | None = None) -> list[Any]:
        """Execute query and fetch all results.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            List of result tuples
        """
        result = self.execute_query(query, parameters)
        return result.fetchall() if result else []

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
        """
        result = self.fetch_one(query, (table_name,))
        return result[0] > 0 if result else False

    def get_table_schema(self, table_name: str) -> list[Any]:
        """Get schema information for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column information tuples
        """
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = ?
            ORDER BY ordinal_position
        """
        return self.fetch_all(query, (table_name,))

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "DatabaseConnection":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit."""
        self.close()
