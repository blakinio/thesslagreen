"""Scanner full/deep scan behavior tests."""

from unittest.mock import AsyncMock, patch

import pytest

from .test_scanner_coverage import _make_scanner, _sized_read_mock


@pytest.mark.asyncio
async def test_deep_scan_skips_none_result():
    """Line 1548: deep_scan=True with None read results → continue."""
    scanner = await _make_scanner(deep_scan=True)
    scanner._client = AsyncMock()

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "raw_registers" in result
    assert result["raw_registers"] == {}

@pytest.mark.asyncio
async def test_deep_scan_collects_values():
    """Line 1547-1550: deep_scan=True with data collects raw_registers."""
    scanner = await _make_scanner(deep_scan=True)
    scanner._client = AsyncMock()

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[42])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "raw_registers" in result
    assert len(result["raw_registers"]) > 0


# ---------------------------------------------------------------------------
# Group M: full_register_scan with invalid holding values (lines 1229-1253)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_input_returns_none():
    """Lines 1198-1202: full_register_scan input read returns None."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {0: "mode"}, 1: {}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert result["failed_addresses"]["modbus_exceptions"]["input_registers"]

@pytest.mark.asyncio
async def test_full_register_scan_holding_invalid_value():
    """Lines 1248-1253: full_register_scan holding has invalid value (65535)."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {0: "mode"}, 1: {}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[1])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=[65535])),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    # 65535 is invalid → should appear in failed_addresses
    assert (
        result["failed_addresses"]["invalid_values"].get("holding_registers")
        or result["unknown_registers"]["holding_registers"]
    )


# ---------------------------------------------------------------------------
# Group N: full_register_scan coil/discrete (lines 1258-1296)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_coil_returns_none():
    """Lines 1261-1265: full_register_scan coil read returns None."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "version_major"}, 3: {}, 1: {0: "some_coil"}, 2: {}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=[1])),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert result["failed_addresses"]["modbus_exceptions"]["coil_registers"]

@pytest.mark.asyncio
async def test_full_register_scan_discrete_returns_value():
    """Lines 1280-1296: full_register_scan discrete reads a value."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {0: "some_discrete"}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=[True])),
    ):
        result = await scanner.scan()

    # discrete read returned [True] — the register at addr 0 should be in
    # available_registers (possibly under the global alias name)
    assert result["available_registers"]["discrete_inputs"]


# ---------------------------------------------------------------------------
# Group S: RTU in scan_device (lines 1669-1675)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_input_no_alias_path():
    """Line 1217: input register not in _names_by_address → add by reg_name."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    # Use addr 0 which IS in global but we clear _names_by_address
    scanner._registers = {4: {0: "fake_input_reg"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {}  # empty → _alias_names returns empty set

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=_sized_read_mock(1)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    # fake_input_reg should be in available_registers (added without alias)
    assert "fake_input_reg" in result["available_registers"]["input_registers"]

@pytest.mark.asyncio
async def test_full_register_scan_input_invalid_value():
    """Lines 1221-1222: input register returns invalid value (65535)."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {0: "fake_input_reg"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=_sized_read_mock(65535)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    # 65535 is invalid → should be in invalid_values
    assert 0 in result["failed_addresses"]["invalid_values"]["input_registers"]


# ---------------------------------------------------------------------------
# Line 1248: full_register_scan holding no-alias path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_holding_no_alias_path():
    """Line 1248: holding register not in _names_by_address → add by reg_name."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {0: "fake_holding_reg"}, 1: {}, 2: {}}
    scanner._names_by_address[3] = {}  # empty → no alias

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=_sized_read_mock(1)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "fake_holding_reg" in result["available_registers"]["holding_registers"]


# ---------------------------------------------------------------------------
# Lines 1266-1275: full_register_scan coil valid response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_coil_valid_with_name():
    """Lines 1266-1275: full_register_scan coil returns data, register in map."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {0: "fake_coil"}, 2: {}}
    scanner._names_by_address[1] = {}  # no alias

    async def coil_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", side_effect=coil_mock),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "fake_coil" in result["available_registers"]["coil_registers"]


# ---------------------------------------------------------------------------
# Lines 1283-1286, 1294-1296: full_register_scan discrete None and valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_discrete_none():
    """Lines 1283-1286: full_register_scan discrete returns None."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {0: "fake_discrete"}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert 0 in result["failed_addresses"]["modbus_exceptions"]["discrete_inputs"]

@pytest.mark.asyncio
async def test_full_register_scan_discrete_valid():
    """Lines 1294-1296: full_register_scan discrete returns valid data."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {}, 1: {}, 2: {0: "fake_discrete"}}
    scanner._names_by_address[2] = {}  # no alias

    async def discrete_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", side_effect=discrete_mock),
    ):
        result = await scanner.scan()

    assert "fake_discrete" in result["available_registers"]["discrete_inputs"]


# ---------------------------------------------------------------------------
# Line 1325: input probe fails → warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_register_scan_coil_alias_path():
    """Line 1271: full_register_scan coil with alias names updates all aliases."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    # addr=0 → "fake_coil" + alias "fake_coil_alias"
    scanner._registers = {4: {}, 3: {}, 1: {0: "fake_coil"}, 2: {}}
    scanner._names_by_address[1] = {0: {"fake_coil", "fake_coil_alias"}}

    async def coil_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", side_effect=coil_mock),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "fake_coil_alias" in result["available_registers"]["coil_registers"]

@pytest.mark.asyncio
async def test_full_register_scan_coil_unknown_addr():
    """Line 1275: full_register_scan coil with address not in _registers[1]."""
    scanner = await _make_scanner(full_register_scan=True, retry=1)
    scanner._client = AsyncMock()
    # coil_max=2, but only addr=2 is registered; addrs 0,1 are unknown
    scanner._registers = {4: {}, 3: {}, 1: {2: "fake_coil"}, 2: {}}
    scanner._names_by_address[1] = {2: {"fake_coil"}}

    async def coil_mock(*args, **kw):
        count = 1
        for a in reversed(args):
            if isinstance(a, int):
                count = a
                break
        return [True] * count

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", side_effect=coil_mock),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    # addrs 0 and 1 should be in unknown_registers
    assert 0 in result["unknown_registers"]["coil_registers"]


# ---------------------------------------------------------------------------
# Line 1296: full_register_scan discrete unknown address
# ---------------------------------------------------------------------------
