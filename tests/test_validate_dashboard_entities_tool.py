from pathlib import Path

from tools.validate_dashboard_entities import validate_dashboard


def test_validate_dashboard_reports_valid_legacy_and_unknown(tmp_path: Path) -> None:
    dashboard = tmp_path / "dashboard.yaml"
    dashboard.write_text(
        """
views:
  - sections:
      - cards:
          - entity: switch.rekuperator_lock_flag
          - entity: switch.rekuperator_lock
          - entity: switch.rekuperator_not_existing
          - entity: number.rekuperator_12
""",
        encoding="utf-8",
    )

    valid, legacy, unknown, suspicious = validate_dashboard(dashboard)

    assert "switch.rekuperator_lock_flag" in valid
    assert legacy == []
    assert unknown == [
        "number.rekuperator_12",
        "switch.rekuperator_lock",
        "switch.rekuperator_not_existing",
    ]
    assert suspicious == ["number.rekuperator_12"]
