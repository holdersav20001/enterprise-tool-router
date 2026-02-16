"""Database connection helper for Postgres."""
import os
from contextlib import contextmanager
from typing import Generator

import psycopg


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self) -> None:
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5433"))
        self.name = os.getenv("DB_NAME", "etr_db")
        self.user = os.getenv("DB_USER", "etr_user")
        self.password = os.getenv("DB_PASSWORD", "etr_password")

    def connection_string(self) -> str:
        """Return PostgreSQL connection string."""
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.name} "
            f"user={self.user} "
            f"password={self.password}"
        )


# Global config instance
_db_config = DatabaseConfig()


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Get a database connection as a context manager.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
    """
    conn = psycopg.connect(_db_config.connection_string())
    try:
        yield conn
    finally:
        conn.close()


def test_connection() -> bool:
    """Test if database connection works.

    Returns:
        True if connection succeeds, False otherwise.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False
