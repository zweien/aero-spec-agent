#!/usr/bin/env python3
"""Summarize QA status from docs/*-qa.md YAML front matter.

Usage: python scripts/summarize_qa_status.py [--json]
"""

import json
import re
import sys
from pathlib import Path


def parse_front_matter(text: str) -> dict | None:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


def main() -> int:
    docs_dir = Path("docs")
    use_json = "--json" in sys.argv
    qa_files = sorted(docs_dir.glob("*qa*.md"))

    entries: list[dict] = []
    for f in qa_files:
        text = f.read_text(encoding="utf-8")
        fm = parse_front_matter(text)
        entries.append({
            "file": f.name,
            "qa_id": fm.get("qa_id", "") if fm else "",
            "status": fm.get("status", "unknown") if fm else "unknown",
            "date": fm.get("date", "") if fm else "",
            "env": fm.get("env", "") if fm else "",
        })

    if use_json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0

    # Table output
    headers = ["File", "QA ID", "Status", "Date", "Env"]
    rows = [[e["file"], e["qa_id"], e["status"], e["date"], e["env"]] for e in entries]

    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    sep = "-+-".join("-" * w for w in widths)

    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*row))

    # Summary
    statuses: dict[str, int] = {}
    for e in entries:
        s = e["status"]
        statuses[s] = statuses.get(s, 0) + 1
    print()
    print(f"Total: {len(entries)}  " + "  ".join(f"{k}: {v}" for k, v in sorted(statuses.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
