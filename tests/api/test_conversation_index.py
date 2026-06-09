"""Tests for ConversationIndex."""

import json
import threading
from pathlib import Path

from services.api.app.services.conversation_index import ConversationIndex


def test_bootstrap_from_existing_conversations(tmp_path: Path):
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    (conv_dir / "c1").mkdir()
    (conv_dir / "c1" / "state.json").write_text(
        json.dumps(
            {
                "conversation_id": "c1",
                "design_id": "c1",
                "messages": [
                    {"role": "user", "content": "设计一架小型无人机"},
                    {"role": "assistant", "content": "好的"},
                ],
            },
            ensure_ascii=False,
        )
    )
    (conv_dir / "c2").mkdir()
    (conv_dir / "c2" / "state.json").write_text(
        json.dumps(
            {
                "conversation_id": "c2",
                "design_id": "c2",
                "messages": [{"role": "user", "content": "hello"}],
            },
            ensure_ascii=False,
        )
    )
    idx = ConversationIndex(root=tmp_path)
    idx.bootstrap()
    entries = idx.list_entries()
    assert len(entries) == 2
    ids = {e["conversation_id"] for e in entries}
    assert ids == {"c1", "c2"}
    c1 = next(e for e in entries if e["conversation_id"] == "c1")
    assert c1["title"] == "设计一架小型无人机"
    assert c1["message_count"] == 2


def test_list_returns_sorted_by_updated_at(tmp_path: Path):
    idx = ConversationIndex(root=tmp_path)
    idx.update_entry("a", title="first", design_id="a")
    idx.update_entry("b", title="second", design_id="b")
    entries = idx.list_entries()
    assert entries[0]["conversation_id"] == "b"


def test_update_entry_upserts(tmp_path: Path):
    idx = ConversationIndex(root=tmp_path)
    idx.update_entry("x", title="hello", design_id="x")
    idx.update_entry("x", title="hello updated", message_count=5, design_id="x")
    entries = idx.list_entries()
    assert len(entries) == 1
    assert entries[0]["title"] == "hello updated"
    assert entries[0]["message_count"] == 5


def test_remove_entry(tmp_path: Path):
    idx = ConversationIndex(root=tmp_path)
    idx.update_entry("a", title="a", design_id="a")
    idx.update_entry("b", title="b", design_id="b")
    idx.remove_entry("a")
    entries = idx.list_entries()
    assert len(entries) == 1
    assert entries[0]["conversation_id"] == "b"


def test_bootstrap_skips_corrupted(tmp_path: Path):
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    (conv_dir / "good").mkdir()
    (conv_dir / "good" / "state.json").write_text(
        json.dumps(
            {"conversation_id": "good", "design_id": "good", "messages": []},
        )
    )
    (conv_dir / "bad").mkdir()
    (conv_dir / "bad" / "state.json").write_text("not json")
    idx = ConversationIndex(root=tmp_path)
    idx.bootstrap()
    entries = idx.list_entries()
    assert len(entries) == 1
    assert entries[0]["conversation_id"] == "good"


def test_concurrent_updates(tmp_path: Path):
    idx = ConversationIndex(root=tmp_path)
    errors: list[Exception] = []

    def writer(n: int):
        try:
            for i in range(50):
                idx.update_entry(
                    f"conv-{n}-{i}", title=f"t{n}-{i}", design_id=f"d{n}"
                )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    entries = idx.list_entries()
    assert len(entries) == 200
