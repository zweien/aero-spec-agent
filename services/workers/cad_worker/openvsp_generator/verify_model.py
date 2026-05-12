from pathlib import Path
from typing import Any


def verification_entry(expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "expected": expected,
        "actual": actual,
        "status": "pass" if actual == expected else "fail",
    }


def verify_vsp3_file(path: Path) -> dict[str, object]:
    actual = path.exists() and path.stat().st_size > 0
    return {
        "expected": True,
        "actual": actual,
        "status": "pass" if actual else "fail",
    }
