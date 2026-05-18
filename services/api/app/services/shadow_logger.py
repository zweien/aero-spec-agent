"""Shadow mode logger for LangGraph divergence tracking."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ShadowLogger:
    """Records divergence between old ChatService and new LangGraph paths."""

    def __init__(self, storage_root: str | Path | None = None) -> None:
        if storage_root is None:
            storage_root = os.environ.get("SHADOW_LOG_DIR", "storage/shadow_logs")
        self._root = Path(storage_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def log_divergence(
        self,
        conversation_id: str,
        user_message: str,
        old_result: dict[str, Any],
        new_result: dict[str, Any],
    ) -> None:
        """Log a divergence event between old and new paths."""
        mismatches = _find_mismatches(old_result, new_result)
        if not mismatches:
            logger.debug("shadow match for conversation_id=%s", conversation_id)
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conversation_id,
            "user_message": user_message[:200],
            "old": old_result,
            "new": new_result,
            "mismatches": mismatches,
        }
        path = self._root / f"{conversation_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(
            "shadow divergence: conversation_id=%s mismatches=%s",
            conversation_id,
            mismatches,
        )


def _find_mismatches(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Compare old and new results, return list of mismatched field names."""
    mismatches = []
    for key in set(list(old.keys()) + list(new.keys())):
        if old.get(key) != new.get(key):
            mismatches.append(key)
    return mismatches
