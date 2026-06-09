"""Thread-safe index of conversations for fast metadata lookups."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class ConversationIndex:
    """Manages a ``conversations_index.json`` file in the storage root.

    Each entry contains: conversation_id, title, created_at, updated_at,
    message_count, design_id.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _path(self) -> Path:
        return self.root / "conversations_index.json"

    def _read(self) -> list[dict]:
        """Read index file, returning an empty list on missing / error."""
        try:
            text = self._path.read_text(encoding="utf-8")
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, entries: list[dict]) -> None:
        """Persist *entries* to the index file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _ts_to_iso(ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_entries(self) -> list[dict]:
        """Return all entries sorted by ``updated_at`` descending."""
        with self._lock:
            entries = self._read()
            entries.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
            return entries

    def get_entry(self, conversation_id: str) -> dict | None:
        """Find one entry by *conversation_id*."""
        with self._lock:
            for entry in self._read():
                if entry.get("conversation_id") == conversation_id:
                    return entry
        return None

    def update_entry(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        message_count: int | None = None,
        design_id: str | None = None,
    ) -> None:
        """Insert or update an entry.

        ``created_at`` is set only on first insert; ``updated_at`` is always
        refreshed.
        """
        now = self._now_iso()
        with self._lock:
            entries = self._read()
            existing = next(
                (e for e in entries if e.get("conversation_id") == conversation_id),
                None,
            )
            if existing is not None:
                if title is not None:
                    existing["title"] = title
                if message_count is not None:
                    existing["message_count"] = message_count
                if design_id is not None:
                    existing["design_id"] = design_id
                existing["updated_at"] = now
            else:
                entries.append(
                    {
                        "conversation_id": conversation_id,
                        "title": title,
                        "created_at": now,
                        "updated_at": now,
                        "message_count": message_count,
                        "design_id": design_id,
                    }
                )
            self._write(entries)

    def remove_entry(self, conversation_id: str) -> None:
        """Remove an entry by *conversation_id*."""
        with self._lock:
            entries = self._read()
            entries = [
                e for e in entries if e.get("conversation_id") != conversation_id
            ]
            self._write(entries)

    def bootstrap(self) -> None:
        """One-time rebuild: scan ``conversations/`` dirs and build the index.

        Reads each ``state.json``, extracts metadata, and creates an index
        entry.  Corrupted / missing files are skipped.
        """
        conv_root = self.root / "conversations"
        if not conv_root.is_dir():
            return

        now = self._now_iso()
        new_entries: list[dict] = []
        try:
            for conv_dir in conv_root.iterdir():
                if not conv_dir.is_dir():
                    continue
                state_file = conv_dir / "state.json"
                if not state_file.is_file():
                    continue
                try:
                    data = json.loads(state_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue

                conv_id = data.get("conversation_id", conv_dir.name)
                messages: list[dict] = data.get("messages", [])
                title = ""
                for msg in messages:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            title = content[:30]
                            break
                stat = state_file.stat()
                new_entries.append(
                    {
                        "conversation_id": conv_id,
                        "title": title,
                        "created_at": self._ts_to_iso(stat.st_ctime),
                        "updated_at": self._ts_to_iso(stat.st_mtime),
                        "message_count": len(messages),
                        "design_id": data.get("design_id"),
                    }
                )
        except OSError:
            return

        with self._lock:
            self._write(new_entries)
