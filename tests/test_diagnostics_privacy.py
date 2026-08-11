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
