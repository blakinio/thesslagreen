#!/usr/bin/env python3
"""Clear legacy airflow statistics after unit change.

Removes statistics entries for the legacy percentage based airflow sensors.

Usage:
    python3 clear_airflow_stats.py [CONFIG_DIR]

If CONFIG_DIR is not provided the script will attempt common locations such as
``~/.homeassistant`` or ``/config``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

LEGACY_SENSORS = [
    "sensor.supply_flow_rate",
    "sensor.exhaust_flow_rate",
]

COMMON_CONFIG_DIRS = [
    Path.home() / ".homeassistant",
    Path.home() / "homeassistant",
    Path("/config"),
]


def find_db(custom: Path | None) -> Path | None:
    if custom:
        db_path = custom / "home-assistant_v2.db"
        return db_path if db_path.exists() else None
    for base in COMMON_CONFIG_DIRS:
        db_path = base / "home-assistant_v2.db"
        if db_path.exists():
            return db_path
    return None


def clear_stats(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for sensor in LEGACY_SENSORS:
        cur.execute(
            "DELETE FROM statistics WHERE metadata_id=(SELECT id FROM statistics_meta WHERE statistic_id=?)",
            (sensor,),
        )
        cur.execute(
            "DELETE FROM statistics_short_term WHERE metadata_id=(SELECT id FROM statistics_meta WHERE statistic_id=?)",
            (sensor,),
        )
        cur.execute(
            "DELETE FROM statistics_meta WHERE statistic_id=?",
            (sensor,),
        )
        print(f"Cleared statistics for {sensor}")
    conn.commit()
    conn.close()


def main() -> None:
    config_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    db_path = find_db(config_dir)
    if not db_path:
        print("Home Assistant database not found")
        return
    clear_stats(db_path)


if __name__ == "__main__":
    main()
