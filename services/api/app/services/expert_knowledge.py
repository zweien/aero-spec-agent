"""Expert-knowledge service.

Loads classical aircraft conceptual-design textbook references from
`packages/expert-knowledge/*.yaml` and exposes lookup helpers used by the
design rule layer and the API.

Each entry carries:
  - topic:       category key (aspect_ratio, wing_loading, ...)
  - applies_to:  list of aircraft category tags
  - metric:      canonical metric name
  - range:       [low, high] preferred window
  - warn_range:  [low, high] acceptable but flagged window
  - sources:     list of {book, chapter, note}

Books are cross-referenced from `books.yaml` so the lookup result can be
rendered with stable citation labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_KNOWLEDGE_DIR = (
    Path(__file__).resolve().parents[4] / "packages" / "expert-knowledge"
)
_BOOKS_FILE = _KNOWLEDGE_DIR / "books.yaml"
_TOPIC_FILES = ["geometry.yaml", "loading.yaml", "aero_performance.yaml"]


@dataclass(frozen=True)
class KnowledgeEntry:
    id: str
    topic: str
    metric: str | None
    applies_to: tuple[str, ...]
    range: tuple[float, float] | None
    warn_range: tuple[float, float] | None
    unit: str
    summary_zh: str
    summary_en: str
    sources: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "metric": self.metric,
            "applies_to": list(self.applies_to),
            "range": list(self.range) if self.range else None,
            "warn_range": list(self.warn_range) if self.warn_range else None,
            "unit": self.unit,
            "summary_zh": self.summary_zh,
            "summary_en": self.summary_en,
            "sources": [dict(s) for s in self.sources],
        }


def _coerce_range(raw: Any) -> tuple[float, float] | None:
    if not raw:
        return None
    if isinstance(raw, list) and len(raw) == 2:
        try:
            return float(raw[0]), float(raw[1])
        except (TypeError, ValueError):
            return None
    return None


@lru_cache(maxsize=1)
def load_books() -> dict[str, dict[str, Any]]:
    if not _BOOKS_FILE.exists():
        return {}
    with open(_BOOKS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("books") or {}
    return raw if isinstance(raw, dict) else {}


@lru_cache(maxsize=1)
def load_entries() -> tuple[KnowledgeEntry, ...]:
    entries: list[KnowledgeEntry] = []
    for filename in _TOPIC_FILES:
        path = _KNOWLEDGE_DIR / filename
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for raw in data.get("entries") or []:
            if not isinstance(raw, dict):
                continue
            sources = raw.get("sources") or []
            sources_clean = tuple(
                {k: v for k, v in src.items() if v is not None}
                for src in sources
                if isinstance(src, dict)
            )
            entries.append(KnowledgeEntry(
                id=str(raw.get("id", "")),
                topic=str(raw.get("topic", "")),
                metric=raw.get("metric") or None,
                applies_to=tuple(raw.get("applies_to") or []),
                range=_coerce_range(raw.get("range")),
                warn_range=_coerce_range(raw.get("warn_range")),
                unit=str(raw.get("unit") or ""),
                summary_zh=str(raw.get("summary_zh") or ""),
                summary_en=str(raw.get("summary_en") or ""),
                sources=sources_clean,
            ))
    return tuple(entries)


def list_topics() -> list[str]:
    return sorted({e.topic for e in load_entries()})


def list_aircraft_categories() -> list[str]:
    cats: set[str] = set()
    for e in load_entries():
        cats.update(e.applies_to)
    return sorted(cats)


def lookup(
    topic: str | None = None,
    aircraft_category: str | None = None,
    metric: str | None = None,
) -> list[KnowledgeEntry]:
    """Return entries that match all provided filters."""
    matches: list[KnowledgeEntry] = []
    for entry in load_entries():
        if topic and entry.topic != topic:
            continue
        if metric and entry.metric != metric:
            continue
        if aircraft_category and aircraft_category not in entry.applies_to:
            continue
        matches.append(entry)
    return matches


def best_range_for(
    topic: str, aircraft_category: str | None = None,
) -> KnowledgeEntry | None:
    """Pick the most specific entry — preferring those whose applies_to
    contains the requested category, falling back to broader entries."""
    candidates = [e for e in load_entries() if e.topic == topic]
    if not candidates:
        return None
    if aircraft_category:
        scoped = [e for e in candidates if aircraft_category in e.applies_to]
        if scoped:
            scoped.sort(key=lambda e: len(e.applies_to))  # prefer narrower
            return scoped[0]
    candidates.sort(key=lambda e: len(e.applies_to))
    return candidates[0]


def render_citation(entry: KnowledgeEntry) -> list[str]:
    """Format an entry's sources into compact citation strings."""
    books = load_books()
    rendered: list[str] = []
    for src in entry.sources:
        book_id = src.get("book")
        info = books.get(book_id, {}) if book_id else {}
        title = info.get("title") or book_id or "unknown"
        chapter = src.get("chapter")
        if chapter:
            rendered.append(f"《{title}》{chapter}")
        else:
            rendered.append(f"《{title}》")
    return rendered


def summarize_lookup(
    topic: str, aircraft_category: str | None = None,
) -> dict[str, Any] | None:
    entry = best_range_for(topic, aircraft_category)
    if entry is None:
        return None
    payload = entry.to_dict()
    payload["citations"] = render_citation(entry)
    return payload
