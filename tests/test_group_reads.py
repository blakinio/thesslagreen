from custom_components.thessla_green_modbus.registers import get_registers_by_function, group_reads


def _expanded_addresses(fn: str) -> list[int]:
    plans = [p for p in group_reads(max_block_size=32) if p.function == fn]
    return [addr for plan in plans for addr in range(plan.address, plan.address + plan.length)]


def test_group_reads_coalesces_per_function():
    for fn in ("01", "02", "03", "04"):
        regs = get_registers_by_function(fn)
        expected = sorted(r.address for r in regs)
        assert _expanded_addresses(fn) == expected
