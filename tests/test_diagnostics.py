from custom_components.thessla_green_modbus.diagnostics import _redact_sensitive_data


def test_redact_ipv4_and_ipv6():
    data = {
        "connection": {"host": "192.168.0.17"},
        "recent_errors": [{"message": "Error contacting 192.168.0.17 and 2001:db8::1"}],
    }

    redacted = _redact_sensitive_data(data)

    assert redacted["connection"]["host"] == "192.xxx.xxx.17"
    message = redacted["recent_errors"][0]["message"]
    assert "192.xxx.xxx.17" in message
    assert "2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:0001" in message


def test_redact_ipv6_connection():
    data = {"connection": {"host": "2001:db8::7334"}}

    redacted = _redact_sensitive_data(data)

    assert redacted["connection"]["host"] == ("2001:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:7334")
