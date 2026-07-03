"""
Azad Foundation MIS - Database Connection Pool
"""
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager
from config import DATABASE_URL

# Parse the DATABASE_URL
# Format: postgresql://user:password@host:port/dbname
_pool = None


def init_pool(minconn=2, maxconn=10):
    """Initialize the connection pool."""
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn, maxconn, DATABASE_URL
        )
    return _pool


def get_pool():
    """Get the connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        init_pool()
    return _pool


@contextmanager
def get_connection():
    """Get a connection from the pool as a context manager."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=None):
    """Get a cursor with automatic connection management."""
    with get_connection() as conn:
        factory = cursor_factory or psycopg2.extras.RealDictCursor
        cursor = conn.cursor(cursor_factory=factory)
        try:
            yield cursor
        finally:
            cursor.close()


def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
