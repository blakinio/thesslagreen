import json
import logging
import shutil
from pathlib import Path
from unittest.mock import call, patch

import pytest

from tools.cleanup_old_entities import cleanup_entity_registry


def _setup_registry(tmp_path: Path, content: str) -> Path:
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    registry_path = storage_dir / "core.entity_registry"
    registry_path.write_text(content, encoding="utf-8")
    return registry_path


def test_cleanup_entity_registry_invalid_json_restores_backup(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    registry_path = _setup_registry(tmp_path, "{invalid")

    with patch("shutil.copy2", wraps=shutil.copy2) as mock_copy:
        with caplog.at_level(logging.ERROR):
            assert not cleanup_entity_registry(tmp_path)  # nosec B101

    backup_path = mock_copy.call_args_list[0].args[1]
    assert "Error decoding entity registry JSON" in caplog.text  # nosec B101
    assert mock_copy.call_args_list == [  # nosec B101
        call(registry_path, backup_path),
        call(backup_path, registry_path),
    ]
    assert registry_path.read_text(encoding="utf-8") == "{invalid"  # nosec B101


def test_cleanup_entity_registry_oserror_restores_backup(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = {
        "data": {
            "entities": [
                {
                    "entity_id": "number.rekuperator_predkosc",
                    "platform": "thessla_green_modbus",
                }
            ]
        }
    }
    registry_path = _setup_registry(tmp_path, json.dumps(original))

    with patch("json.dump", side_effect=OSError("disk error")):
        with patch("shutil.copy2", wraps=shutil.copy2) as mock_copy:
            with caplog.at_level(logging.ERROR):
                assert not cleanup_entity_registry(tmp_path)  # nosec B101

    backup_path = mock_copy.call_args_list[0].args[1]
    assert "Error processing entity registry file" in caplog.text  # nosec B101
    assert mock_copy.call_args_list == [  # nosec B101
        call(registry_path, backup_path),
        call(backup_path, registry_path),
    ]
    assert json.loads(registry_path.read_text(encoding="utf-8")) == original  # nosec B101


def test_cleanup_entity_registry_removes_aliases(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = {
        "data": {
            "entities": [
                {
                    "entity_id": "number.rekuperator_predkosc",
                    "platform": "thessla_green_modbus",
                },
                {
                    "entity_id": "number.rekuperator_speed",
                    "platform": "thessla_green_modbus",
                },
                {
                    "entity_id": "fan.valid_entity",
                    "platform": "thessla_green_modbus",
                },
            ]
        }
    }
    registry_path = _setup_registry(tmp_path, json.dumps(original))

    with caplog.at_level(logging.INFO):
        assert cleanup_entity_registry(tmp_path)  # nosec B101

    result = json.loads(registry_path.read_text(encoding="utf-8"))
    entities = result["data"]["entities"]

    # Only the valid entity should remain
    assert entities == [  # nosec B101
        {
            "entity_id": "fan.valid_entity",
            "platform": "thessla_green_modbus",
        }
    ]
    assert "Found 2 old entities to remove" in caplog.text  # nosec B101
