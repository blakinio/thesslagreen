import logging

from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_mark_input_unsupported_merges_overlaps():
    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)
    scanner._mark_input_unsupported(0x0000, 0x0002, 1)
    scanner._mark_input_unsupported(0x0001, 0x0003, 1)
    assert scanner._unsupported_input_ranges == {(0x0000, 0x0003): 1}


def test_log_skipped_ranges_no_duplicate_spans(caplog):
    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)
    scanner._mark_input_unsupported(0x0010, 0x0012, 2)
    scanner._mark_input_unsupported(0x0011, 0x0014, 2)

    with caplog.at_level(logging.WARNING):
        scanner._log_skipped_ranges()

    assert "0x0010-0x0014" in caplog.text
    assert "0x0010-0x0012" not in caplog.text
    assert "0x0011-0x0014" not in caplog.text
