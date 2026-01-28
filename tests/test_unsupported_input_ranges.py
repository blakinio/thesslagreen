import logging

from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner


def test_mark_input_unsupported_merges_overlaps():
    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)
    scanner._mark_input_unsupported(0, 2, 1)
    scanner._mark_input_unsupported(1, 3, 1)
    assert scanner._unsupported_input_ranges == {(0, 3): 1}


def test_log_skipped_ranges_no_duplicate_spans(caplog):
    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)
    scanner._mark_input_unsupported(16, 18, 2)
    scanner._mark_input_unsupported(17, 20, 2)

    with caplog.at_level(logging.WARNING):
        scanner._log_skipped_ranges()

    assert "16-20" in caplog.text
    assert "16-18" not in caplog.text
    assert "17-20" not in caplog.text
