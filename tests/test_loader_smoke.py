from custom_components.thessla_green_modbus.modbus_helpers import group_reads
from custom_components.thessla_green_modbus.registers import get_all_registers


def test_loader_smoke():
    regs = get_all_registers()
    assert regs
    addresses = []
    for reg in regs:
        addresses.extend(range(reg.address, reg.address + reg.length))
    plans = group_reads(addresses)
    assert plans
