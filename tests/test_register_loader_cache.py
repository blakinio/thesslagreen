"""Split register loader tests."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.cache import registers_sha256
from custom_components.thessla_green_modbus.registers.loader import (
    clear_cache,
    get_registers_path,
    load_registers,
)


def _add_desc(reg: dict) -> dict:
    return {**reg, "description": reg.get("description", "desc"), "description_en": reg.get("description_en", "desc")}


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))

def test_register_cache_invalidation(tmp_path, monkeypatch) -> None:
    """Ensure register file caching and invalidation behave correctly."""

    # Use a temporary copy of the register file so we can modify it
    path = tmp_path / "regs.json"
    path.write_text(get_registers_path().read_text())

    read_calls = 0
    hash_calls = 0
    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes

    def spy_read(self, *args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        text = real_read_text(self, *args, **kwargs)
        json.loads(text)
        return text

    def spy_read_bytes(self):
        nonlocal hash_calls
        hash_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_text", spy_read)
    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    clear_cache()

    hash_before = registers_sha256(path)
    load_registers(path)
    load_registers(path)

    assert read_calls == 1
    assert hash_calls == 1

    path.write_text(real_read_text(path) + "\n")

    load_registers(path)
    hash_after = registers_sha256(path)

    assert read_calls == 2
    assert hash_calls == 2
    assert hash_before != hash_after

def test_registers_sha256_uses_cache(tmp_path, monkeypatch) -> None:
    """registers_sha256 should avoid re-reading unchanged files."""

    import os

    path = tmp_path / "regs.json"
    path.write_text("data")
    mtime = path.stat().st_mtime

    read_calls = 0
    real_read_bytes = Path.read_bytes

    def spy_read_bytes(self):
        nonlocal read_calls
        read_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    digest1 = registers_sha256(path)
    digest2 = registers_sha256(path)

    assert digest1 == digest2
    assert read_calls == 1

    path.write_text("data2")
    os.utime(path, (mtime + 1, mtime + 1))
    registers_sha256(path)

    assert read_calls == 2

def test_registers_reload_on_file_change(tmp_path) -> None:
    """Changing the register JSON file triggers a reload."""

    path = tmp_path / "regs.json"
    path.write_text(get_registers_path().read_text())

    clear_cache()

    original = load_registers(path)
    assert not any(r.name == "cache_test_marker" for r in original)

    data = json.loads(path.read_text())
    data["registers"][0]["name"] = "cache_test_marker"
    path.write_text(json.dumps(data))

    updated = load_registers(path)
    assert any(r.name == "cache_test_marker" for r in updated)

def test_clear_cache_resets_file_hash(tmp_path, monkeypatch) -> None:
    """clear_cache should reset the cached file hash."""

    path = tmp_path / "regs.json"
    path.write_text(get_registers_path().read_text())

    hash_calls = 0
    real_read_bytes = Path.read_bytes

    def spy_read_bytes(self):
        nonlocal hash_calls
        hash_calls += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)

    clear_cache()

    # First load computes hash once
    load_registers(path)
    load_registers(path)
    assert hash_calls == 1

    # Clearing the cache forces a re-computation
    clear_cache()
    load_registers(path)
    assert hash_calls == 2
