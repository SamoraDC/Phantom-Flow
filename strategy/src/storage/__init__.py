"""Storage module for persisting trades and state."""

from .database import Database, init_database

__all__ = ["Database", "init_database"]
