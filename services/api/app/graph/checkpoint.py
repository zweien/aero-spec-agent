"""Checkpointer factory — InMemorySaver or SqliteSaver for graph persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver


def make_memory_checkpointer() -> InMemorySaver:
    """Create an in-memory checkpointer (no persistence across restarts)."""
    return InMemorySaver()


def make_sqlite_checkpointer(db_path: str | Path | None = None) -> "SqliteSaver":
    """Create a SQLite checkpointer for thread-based persistence.

    Args:
        db_path: Path to the SQLite database file. None defaults to
                 storage/langgraph/checkpoints.sqlite.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    if db_path is None:
        db_path = Path("storage/langgraph/checkpoints.sqlite")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
