"""Cache and async behavior tests for register loader."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.cache import (
    async_registers_sha256,
    get_cached_file_info,
    get_cached_registers,
)
from custom_components.thessla_green_modbus.registers.loader import clear_cache, load_registers
from custom_components.thessla_green_modbus.registers.register_def import RegisterDef


def _add_desc(reg: dict) -> dict:
    return {
        **reg,
        "description": reg.get("description", "desc"),
        "description_en": reg.get("description_en", "desc"),
    }


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))


def test_decode_multi_register_string_unicode_error_recovery() -> None:
    """Invalid UTF-8 bytes should be decoded with replacement characters."""
    reg = RegisterDef(
        function=3,
        address=0,
        name="label",
        access="ro",
        length=2,
        extra={"type": "string", "encoding": "utf-8"},
    )
    # Bytes 0xFF, 0x10, 0xFE, 0x20 are invalid in strict UTF-8
    result = reg.decode([0xFF10, 0xFE20])
    assert isinstance(result, str)
    assert "\ufffd" in result  # U+FFFD replacement character


async def test_async_registers_sha256_computes_and_caches(tmp_path: Path) -> None:
    """async_registers_sha256 returns a deterministic digest for unchanged files."""
    path = tmp_path / "regs.json"
    path.write_text('{"registers": []}')
    clear_cache()

    h1 = await async_registers_sha256(None, path)
    assert isinstance(h1, str) and len(h1) == 64

    # Second call with same mtime → returns cached value (no re-read)
    h2 = await async_registers_sha256(None, path)
    assert h1 == h2


async def test_async_load_registers_populates_cache(tmp_path: Path) -> None:
    """async_load_registers should populate and reuse the register list cache."""
    from custom_components.thessla_green_modbus.registers.loader import (
        async_load_registers,
    )

    _write(
        tmp_path / "regs.json",
        [
            {"function": "03", "address_dec": 5, "name": "r1", "access": "R"},
        ],
    )
    clear_cache()

    regs = await async_load_registers(None, tmp_path / "regs.json")
    assert isinstance(regs, list)
    assert any(r.name == "r_1" for r in regs)

    # Second call: returns same cached list
    regs2 = await async_load_registers(None, tmp_path / "regs.json")
    assert regs is regs2


async def test_async_get_registers_by_function_filters(tmp_path: Path) -> None:
    """async_get_registers_by_function should normalize and filter function code."""
    from custom_components.thessla_green_modbus.registers.loader import (
        async_get_registers_by_function,
    )

    _write(
        tmp_path / "regs.json",
        [
            {"function": "03", "address_dec": 0, "name": "hold_reg", "access": "R"},
            {"function": "04", "address_dec": 0, "name": "inp_reg", "access": "R"},
        ],
    )
    clear_cache()

    regs = await async_get_registers_by_function(None, 3, tmp_path / "regs.json")
    assert all(r.function == 3 for r in regs)
    assert any(r.name == "hold_reg" for r in regs)
    assert not any(r.name == "inp_reg" for r in regs)


def test_cache_helpers_expose_cached_state_via_public_api(tmp_path: Path) -> None:
    """Cache helper functions should expose hash/register cache state."""
    path = tmp_path / "regs.json"
    _write(path, [{"function": "03", "address_dec": 0, "name": "r", "access": "R"}])
    clear_cache()

    regs = load_registers(path)
    file_info = get_cached_file_info(path)
    assert file_info is not None
    mtime, digest = file_info
    assert isinstance(digest, str) and len(digest) == 64
    assert get_cached_registers(digest, mtime) is regs
