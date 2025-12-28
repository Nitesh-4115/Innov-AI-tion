"""
Database connection and session management for AdherenceGuardian
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from config import settings


# Create SQLAlchemy engine
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite specific configuration
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DATABASE_ECHO
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL or other databases
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes to get database session.
    Automatically closes session after request.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database session.
    Use this for background tasks or non-FastAPI contexts.
    
    Usage:
        with get_db_context() as db:
            db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.
    Creates all tables defined in models.
    """
    # Import models to register them with Base
    import models  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {settings.DATABASE_URL}")


def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)
    print("All database tables dropped")


def reset_db() -> None:
    """
    Reset database by dropping and recreating all tables.
    WARNING: This will delete all data!
    """
    drop_db()
    init_db()
    print("Database reset complete")


class DatabaseHealthCheck:
    """Database health check utilities"""
    
    @staticmethod
    def is_connected() -> bool:
        """Check if database is connected"""
        try:
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_table_counts() -> dict:
        """Get row counts for all tables"""
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        counts = {}
        with get_db_context() as db:
            for table in tables:
                result = db.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = result.scalar()
        
        return counts


# Export commonly used items
__all__ = [
    "engine",
    "SessionLocal", 
    "Base",
    "get_db",
    "get_db_context",
    "init_db",
    "drop_db",
    "reset_db",
    "DatabaseHealthCheck"
]
