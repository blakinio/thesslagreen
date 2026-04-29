from custom_components.thessla_green_modbus.registers.codec import (
    apply_output_scaling,
    coerce_scaled_input,
    decode_bitmask_value,
    decode_enum_value,
    encode_enum_value,
)


def test_decode_enum_value_str_key() -> None:
    assert decode_enum_value(1, {"1": "on"}) == "on"


def test_decode_bitmask_value_sorted() -> None:
    assert decode_bitmask_value(5, {4: "c", 1: "a", 2: "b"}) == ["a", "c"]


def test_encode_enum_value() -> None:
    assert encode_enum_value("on", {0: "off", 1: "on"}, "mode") == 1


def test_apply_output_scaling() -> None:
    assert apply_output_scaling(10, 0.5, 0.5) == 5.0


def test_coerce_scaled_input_resolution_multiplier() -> None:
    scaled = coerce_scaled_input(
        value=12.0,
        raw_value=12.0,
        minimum=0,
        maximum=100,
        multiplier=0.5,
        resolution=0.5,
        name="x",
    )
    assert int(scaled) == 24
