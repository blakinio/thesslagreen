from custom_components.thessla_green_modbus.modbus_helpers import group_reads
from custom_components.thessla_green_modbus.registers import get_all_registers
from custom_components.thessla_green_modbus.registers import (
    get_all_registers,
    plan_group_reads,
)

def test_loader_smoke():
    regs = get_all_registers()
    assert regs
    addresses = []
    for reg in regs:
        addresses.extend(range(reg.address, reg.address + reg.length))
    plans = group_reads(addresses)
    plans = plan_group_reads()
    assert plans
