from __future__ import annotations

from typing import Any


def is_unmappable_holding_register(register: str, all_mappings: tuple[dict[str, Any], ...], binary_mappings: dict[str, Any]) -> bool:
    return any(register in mapping for mapping in all_mappings) or any(v.get('register') == register for v in binary_mappings.values())


def register_context(reg: Any) -> tuple[str, str, Any, Any, Any, str, Any, Any]:
    return (
        reg.name,
        (reg.access or '').upper(),
        reg.min,
        reg.max,
        reg.unit,
        reg.information or '',
        reg.multiplier or 1,
        reg.resolution or (reg.multiplier or 1),
    )


def is_problem_register(register: str) -> bool:
    return register in {'alarm', 'error'} or register.startswith(('s_', 'e_', 'f_'))
