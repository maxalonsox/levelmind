from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


class DatabaseConnectionError(RuntimeError):
    """Raised when the database connectivity check fails."""


def check_database_connection() -> None:
    """Verify database connectivity without changing persisted data."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError("Database connectivity check failed") from exc

    if result != 1:
        raise DatabaseConnectionError("Database connectivity check returned no result")
