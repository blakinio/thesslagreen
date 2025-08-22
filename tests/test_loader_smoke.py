from custom_components.thessla_green_modbus.registers import get_all_registers, group_reads


def test_loader_smoke():
    regs = get_all_registers()
    assert regs
    plans = group_reads()
    assert plans
