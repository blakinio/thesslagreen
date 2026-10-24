"""Privacy regressions for diagnostics endpoint redaction."""

from custom_components.thessla_green_modbus.diagnostics import _redact_sensitive_data


def test_redact_internal_hostname_and_error_message() -> None:
    """A valid internal hostname must not leak through diagnostics or recent errors."""
    data = {
        "connection": {"host": "airpack.local"},
        "recent_errors": [{"message": "Connection to airpack.local timed out"}],
    }

    redacted = _redact_sensitive_data(data)

    assert redacted["connection"]["host"] == "<redacted-host>"
    assert redacted["recent_errors"][0]["message"] == ("Connection to <redacted-host> timed out")


def test_redact_single_label_hostname() -> None:
    """DHCP-style single-label hostnames are sensitive too."""
    redacted = _redact_sensitive_data({"connection": {"host": "airpack123"}})

    assert redacted["connection"]["host"] == "<redacted-host>"


def test_invalid_non_hostname_string_keeps_legacy_fallback() -> None:
    """Arbitrary non-IP, non-host strings are not rewritten as hostnames."""
    redacted = _redact_sensitive_data({"connection": {"host": "not_a_valid_ip_address"}})

    assert redacted["connection"]["host"] == "not_a_valid_ip_address"


def test_redact_nested_serial_and_raw_serial_words() -> None:
    """Serial numbers nested in scan results and raw FC04 24-29 words are masked."""
    data = {
        "device_info": {"serial_number": "1A2B3C4D5E6F"},
        "scan_result": {
            "device_info": {"serial_number": "1A2B3C4D5E6F"},
            "raw_registers": {16: 215, 24: 0x1A2B, 29: 0x5E6F},
        },
        "raw_registers": {"24": 0x1A2B, "30": 7},
    }

    redacted = _redact_sensitive_data(data)

    assert redacted["device_info"]["serial_number"] == "1A***6F"
    assert redacted["scan_result"]["device_info"]["serial_number"] == "1A***6F"
    assert redacted["scan_result"]["raw_registers"] == {
        16: 215,
        24: "**REDACTED**",
        29: "**REDACTED**",
    }
    assert redacted["raw_registers"] == {"24": "**REDACTED**", "30": 7}
    assert data["scan_result"]["raw_registers"][24] == 0x1A2B
