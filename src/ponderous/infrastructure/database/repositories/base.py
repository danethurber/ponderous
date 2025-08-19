"""Base repository class for common database operations."""

from typing import Any

from ponderous.infrastructure.database.connection import DatabaseConnection


class BaseRepository:
    """Abstract base repository for database operations."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """Initialize repository with database connection.

        Args:
            db_connection: Database connection manager
        """
        self.db = db_connection

    def execute_query(self, query: str, parameters: tuple | None = None) -> Any:
        """Execute a query with optional parameters.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Query result
        """
        return self.db.execute_query(query, parameters)

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
        return self.db.fetch_one(query, parameters)

    def fetch_all(self, query: str, parameters: tuple | None = None) -> list[Any]:
        """Execute query and fetch all results.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            List of result tuples
        """
        return self.db.fetch_all(query, parameters)

    def execute_many(self, query: str, parameters_list: list) -> None:
        """Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            parameters_list: List of parameter tuples
        """
        self.db.execute_many(query, parameters_list)
