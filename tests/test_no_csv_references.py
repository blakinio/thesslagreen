"""Ensure repository has no stray CSV references."""

from __future__ import annotations

from pathlib import Path


def test_no_csv_references() -> None:
    """Fail if any ``*.csv`` files exist outside legacy directories."""

    repo_root = Path(__file__).resolve().parent.parent
    csv_files = [
        p
        for p in repo_root.rglob("*.csv")
        if not any(part in {"legacy", "data"} for part in p.parts)
    ]
    assert not csv_files, f"Unexpected CSV files found: {csv_files}"

