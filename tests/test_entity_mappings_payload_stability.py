from types import SimpleNamespace

from custom_components.thessla_green_modbus.mappings._mapping_extend_common import (
    is_problem_register,
    is_unmappable_holding_register,
    register_context,
)


def test_is_problem_register_patterns():
    assert is_problem_register("alarm")
    assert is_problem_register("s_foo")
    assert not is_problem_register("normal_register")


def test_is_unmappable_holding_register_checks_existing_and_source_register():
    mapped = ({"foo": {}},)
    assert is_unmappable_holding_register("foo", mapped, {})
    assert is_unmappable_holding_register("source", ({},), {"x": {"register": "source"}})
    assert not is_unmappable_holding_register("free", ({},), {})


def test_register_context_normalization():
    reg = SimpleNamespace(
        name="r",
        access="rw",
        min=1,
        max=2,
        unit="%",
        information=None,
        multiplier=2,
        resolution=None,
    )
    assert register_context(reg) == ("r", "RW", 1, 2, "%", "", 2, 2)
