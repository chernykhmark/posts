# db/__init__.py

from db.pool import Database, get_db, init_db, close_db

__all__ = ["Database", "get_db", "init_db", "close_db"]