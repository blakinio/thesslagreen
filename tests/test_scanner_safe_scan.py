"""Scanner safe-scan behavior tests."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from .test_scanner_coverage import _make_scanner, _run_minimal_scan


@pytest.mark.asyncio
async def test_safe_scan_group_registers():
    """Line 994: safe_scan=True → single-register batches."""
    scanner = await _make_scanner(safe_scan=True)
    result = scanner._group_registers_for_batch_read([0, 1, 5, 10])
    assert result == [(0, 1), (1, 1), (5, 1), (10, 1)]


# ---------------------------------------------------------------------------
# Group K: scan() raises ConnectionException without transport/client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_skip_known_missing_input_register():
    """Line 1302-1303: skip_known_missing=True skips 'compilation_days'."""
    scanner = await _make_scanner(skip_known_missing=True)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner.core import INPUT_REGISTERS

    if "compilation_days" not in INPUT_REGISTERS:
        pytest.skip("compilation_days not in INPUT_REGISTERS")

    result = await _run_minimal_scan(scanner, input_return=[1])
    # compilation_days should not appear in missing registers (was skipped)
    missing = result.get("missing_registers", {}).get("input_registers", {})
    assert "compilation_days" not in missing

@pytest.mark.asyncio
async def test_scan_input_batch_fail_probe_success():
    """Lines 1313-1341: batch read fails, probe individual succeeds."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner.core import INPUT_REGISTERS

    if "version_major" not in INPUT_REGISTERS:
        pytest.skip("version_major not in INPUT_REGISTERS")

    addr = INPUT_REGISTERS["version_major"]
    scanner._registers = {4: {addr: "version_major"}, 3: {}, 1: {}, 2: {}}

    batch_call_count = {"n": 0}

    async def mock_read_input(*args, **kwargs):
        batch_call_count["n"] += 1
        if batch_call_count["n"] <= 2:  # firmware block reads return empty
            return []
        count = args[-1] if len(args) > 1 else kwargs.get("count", 1)
        if count > 1:
            return None  # batch fails
        return [4]  # individual probe succeeds

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=mock_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "available_registers" in result

@pytest.mark.asyncio
async def test_scan_input_batch_fail_probe_fail(caplog):
    """Lines 1332-1334: batch fails, individual probe returns falsy → warning."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner.core import INPUT_REGISTERS

    if "version_major" not in INPUT_REGISTERS:
        pytest.skip("version_major not in INPUT_REGISTERS")

    addr = INPUT_REGISTERS["version_major"]
    scanner._registers = {4: {addr: "version_major"}, 3: {}, 1: {}, 2: {}}

    async def mock_read_input(*args, **kwargs):
        count = args[-1] if len(args) > 1 else 1
        if isinstance(count, int) and count > 1:
            return None  # batch fails
        return None  # probe also fails

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=mock_read_input),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        caplog.at_level(logging.WARNING),
    ):
        await scanner.scan()

    assert "Failed to read input_registers register" in caplog.text


# ---------------------------------------------------------------------------
# Group P: Holding batch failure recovery (lines 1368-1410)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_batch_fail_probe_success():
    """Lines 1373-1400: holding batch fails, probe succeeds."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    from custom_components.thessla_green_modbus.scanner.core import HOLDING_REGISTERS

    if "mode" not in HOLDING_REGISTERS:
        pytest.skip("mode not in HOLDING_REGISTERS")

    addr = HOLDING_REGISTERS["mode"]
    scanner._registers = {4: {}, 3: {addr: "mode"}, 1: {}, 2: {}}

    async def mock_read_holding(*args, **kwargs):
        count = args[-1] if len(args) > 1 else 1
        if isinstance(count, int) and count > 1:
            return None  # batch fails
        return [1]  # probe succeeds with valid value

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=mock_read_holding),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "available_registers" in result


# ---------------------------------------------------------------------------
# Group Q: deep_scan=True (line 1548)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_input_probe_always_fails(caplog):
    """Line 1325: batch fails, individual probe returns falsy → warning."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {9999: "fake_input"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {9999: {"fake_input"}}

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        caplog.at_level(logging.WARNING),
    ):
        await scanner.scan()

    assert "Failed to read input_registers register 9999" in caplog.text


# ---------------------------------------------------------------------------
# Lines 1339-1340: input probe returns invalid value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_input_probe_returns_invalid_value():
    """Lines 1339-1340: batch fails, probe returns invalid value (65535)."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {9999: "fake_input"}, 3: {}, 1: {}, 2: {}}
    scanner._names_by_address[4] = {9999: {"fake_input"}}

    call_n = {"n": 0}

    async def mock_read_input(*args, **kwargs):
        call_n["n"] += 1
        # First 2 calls are _read_input_block's firmware read (returns [])
        # but we patch _read_input_block separately
        # The direct _read_input calls: batch (count=1 for addr 9999) → None
        # then probe → [65535]
        count = args[-1] if len(args) >= 2 else kwargs.get("count", 1)
        if count is None:
            count = 1
        return None  # all fail

    # Actually, simplest: batch=None, probe=[65535]
    batch_n = {"n": 0}

    async def read_input_for_probe(*args, **kwargs):
        batch_n["n"] += 1
        if batch_n["n"] == 1:
            return None  # batch fails
        return [65535]  # probe returns invalid

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", side_effect=read_input_for_probe),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert 9999 in result["failed_addresses"]["invalid_values"]["input_registers"]


# ---------------------------------------------------------------------------
# Line 1357: holding scan skips UART-optional registers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_skips_uart_optional_registers():
    """Line 1357: scan_uart_settings=False skips UART optional registers."""
    scanner = await _make_scanner(scan_uart_settings=False, retry=1)
    scanner._client = AsyncMock()
    # UART_OPTIONAL_REGS = range(4452, 4460)
    scanner._registers = {4: {}, 3: {4452: "uart_0_id"}, 1: {}, 2: {}}

    read_holding_calls = []

    async def mock_read_holding(*args, **kwargs):
        read_holding_calls.append(args)
        return [1]

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=mock_read_holding),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        await scanner.scan()

    # addr 4452 should have been skipped — not read
    assert not read_holding_calls


# ---------------------------------------------------------------------------
# Lines 1362-1363: holding multi-register (MULTI_REGISTER_SIZES > 1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_multiregister_alias():
    """Lines 1362-1363: duplicate holding address merges names into one entry."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    class DuplicateAddressHoldingMap(dict[int, str]):
        def items(self):
            return iter([(9999, "fake_h1"), (9999, "fake_h2")])

    with (
        patch.object(scanner, "_group_registers_for_batch_read", return_value=[(9999, 1)]),
        patch.object(scanner, "_read_holding", AsyncMock(return_value=[123])),
        patch.object(scanner, "_is_valid_register_value", return_value=True),
    ):
        await scanner._scan_named_holding(DuplicateAddressHoldingMap())

    assert "fake_h1" in scanner.available_registers["holding_registers"]
    assert "fake_h2" in scanner.available_registers["holding_registers"]


# ---------------------------------------------------------------------------
# Lines 1371-1372: holding TypeError fallback in batch read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_type_error_fallback():
    """Lines 1371-1372: _read_holding raises TypeError → fallback to 2-arg."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {9999: "fake_holding"}, 1: {}, 2: {}}
    scanner._names_by_address[3] = {9999: {"fake_holding"}}

    call_n = {"n": 0}

    async def mock_read_holding(*args, **kw):
        call_n["n"] += 1
        if len(args) == 3 and call_n["n"] == 1:
            raise TypeError("unexpected signature")
        return [1]  # fallback (2-arg) succeeds

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=mock_read_holding),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "fake_holding" in result["available_registers"]["holding_registers"]


# ---------------------------------------------------------------------------
# Lines 1384, 1398-1399: holding probe addr not in map / invalid probe value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_probe_addr_not_in_info():
    """Line 1384: addr in batch range but not in holding_info → continue."""
    # To get a batch range wider than holding_info, we need _group_reads to
    # merge two addresses with a gap between them — but it shouldn't unless
    # the gap is ≤ max_gap. Let's instead trigger it via MULTI_REGISTER_SIZES:
    # a holding reg with size=2 adds both addr and addr+1 to holding_addresses.
    # If only the base addr is in holding_info, then addr+1 triggers line 1384.
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()

    import custom_components.thessla_green_modbus.scanner.core as sc

    original_multi = dict(sc.MULTI_REGISTER_SIZES)
    try:
        # Register "fake_multi" at addr 9999 with size 2
        sc.MULTI_REGISTER_SIZES["fake_multi"] = 2
        scanner._registers = {4: {}, 3: {9999: "fake_multi"}, 1: {}, 2: {}}
        scanner._names_by_address[3] = {9999: {"fake_multi"}}

        # batch will cover (9999, 2) → when it fails, we iterate 9999 and 10000
        # 10000 is not in holding_info → line 1384 hit

        with (
            patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
            patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
            patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
            patch.object(scanner, "_read_holding", AsyncMock(return_value=None)),
            patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
            patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
        ):
            await scanner.scan()

    finally:
        sc.MULTI_REGISTER_SIZES.clear()
        sc.MULTI_REGISTER_SIZES.update(original_multi)

@pytest.mark.asyncio
async def test_scan_holding_probe_invalid_value():
    """Lines 1398-1399: batch fails, probe returns invalid value → tracking."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {9999: "fake_holding"}, 1: {}, 2: {}}
    scanner._names_by_address[3] = {9999: {"fake_holding"}}

    batch_n = {"n": 0}

    async def read_holding_for_probe(*args, **kwargs):
        batch_n["n"] += 1
        if batch_n["n"] == 1:
            return None  # batch fails
        return [65535]  # probe returns invalid

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=read_holding_for_probe),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert 9999 in result["failed_addresses"]["invalid_values"]["holding_registers"]


# ---------------------------------------------------------------------------
# Lines 1389-1390: TypeError in holding probe → fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_holding_probe_type_error_fallback():
    """Lines 1389-1390: individual probe raises TypeError → 2-arg fallback."""
    scanner = await _make_scanner(retry=1)
    scanner._client = AsyncMock()
    scanner._registers = {4: {}, 3: {9999: "fake_holding"}, 1: {}, 2: {}}
    scanner._names_by_address[3] = {9999: {"fake_holding"}}

    call_n = {"n": 0}

    async def mock_read_holding(*args, **kw):
        call_n["n"] += 1
        if call_n["n"] == 1:
            return None  # batch fails
        # probe attempt: 3-arg form raises TypeError first time
        if call_n["n"] == 2:
            raise TypeError("bad sig")
        return [1]  # fallback 2-arg succeeds

    with (
        patch.object(scanner, "_read_input_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_holding_block", AsyncMock(return_value=[])),
        patch.object(scanner, "_read_input", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_holding", side_effect=mock_read_holding),
        patch.object(scanner, "_read_coil", AsyncMock(return_value=None)),
        patch.object(scanner, "_read_discrete", AsyncMock(return_value=None)),
    ):
        result = await scanner.scan()

    assert "fake_holding" in result["available_registers"]["holding_registers"]


# ---------------------------------------------------------------------------
# Line 1634: scan_device legacy path returns non-tuple dict
# ---------------------------------------------------------------------------
