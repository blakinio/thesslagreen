from custom_components.thessla_green_modbus.registers.loader import (
    get_all_registers,
    get_registers_by_function,
    group_reads,
)


def test_get_all_registers():
    regs = get_all_registers()
    assert regs, "No registers loaded"


def test_get_registers_by_function():
    all_regs = get_all_registers()
    fn = all_regs[0].function
    filtered = get_registers_by_function(fn)
    assert all(r.function == fn for r in filtered)


def test_group_reads():
    plans = group_reads(max_block_size=10)
    assert plans, "No read plans generated"
    for plan in plans:
        assert plan.length <= 10
