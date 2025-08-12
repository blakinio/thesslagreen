import json
import logging
import shutil
from pathlib import Path
from unittest.mock import call, patch

from custom_components.thessla_green_modbus.cleanup_old_entities import (
    cleanup_entity_registry,
)


def _setup_registry(tmp_path: Path, content: str) -> Path:
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    registry_path = storage_dir / "core.entity_registry"
    registry_path.write_text(content, encoding="utf-8")
    return registry_path


def test_cleanup_entity_registry_invalid_json_restores_backup(tmp_path, caplog):
    registry_path = _setup_registry(tmp_path, "{invalid")

    with patch("shutil.copy2", wraps=shutil.copy2) as mock_copy:
        with caplog.at_level(logging.ERROR):
            assert not cleanup_entity_registry(tmp_path)

    backup_path = mock_copy.call_args_list[0].args[1]
    assert "Error decoding entity registry JSON" in caplog.text
    assert mock_copy.call_args_list == [call(registry_path, backup_path), call(backup_path, registry_path)]
    assert registry_path.read_text(encoding="utf-8") == "{invalid"


def test_cleanup_entity_registry_oserror_restores_backup(tmp_path, caplog):
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
                assert not cleanup_entity_registry(tmp_path)

    backup_path = mock_copy.call_args_list[0].args[1]
    assert "Error processing entity registry file" in caplog.text
    assert mock_copy.call_args_list == [call(registry_path, backup_path), call(backup_path, registry_path)]
    assert json.loads(registry_path.read_text(encoding="utf-8")) == original
