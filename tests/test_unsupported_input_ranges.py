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


def test_log_skipped_ranges_omits_addresses_already_covered(caplog):
    scanner = ThesslaGreenDeviceScanner("1.2.3.4", 502, 10)
    scanner._mark_input_unsupported(2, 15, 2)
    scanner._mark_input_unsupported(298, 298, 2)
    scanner._mark_holding_unsupported(15, 30, 2)
    scanner._mark_holding_unsupported(240, 241, 2)

    scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(range(0, 26))
    scanner.failed_addresses["modbus_exceptions"]["input_registers"].add(298)
    scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(range(15, 31))
    scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update({240, 241})

    with caplog.at_level(logging.WARNING):
        scanner._log_skipped_ranges()

    assert "Skipping unsupported input registers 2-15" in caplog.text
    assert "Skipping unsupported holding registers 15-30" in caplog.text
    assert "Failed to read input_registers at 0, 1, 16" in caplog.text
    assert "298" not in caplog.text.split("Failed to read input_registers at ")[1].split("\n")[0]
    assert "Failed to read holding_registers at" not in caplog.text
