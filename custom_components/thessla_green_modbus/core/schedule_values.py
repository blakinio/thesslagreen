"""Pure AATT construction; FC03 schedule settings hold airflow AND temperature."""

from __future__ import annotations

from typing import Any


def complete_schedule_value(value: Any, current: Any) -> dict[str, Any]:
    """Fill an omitted temperature from a fresh decoded device word or fail."""
    if isinstance(value, dict):
        airflow = value.get("airflow_pct", value.get("airflow"))
        temperature = value.get("temp_c", value.get("temp"))
        if value.get("temp_unset") is True:
            if temperature is not None or airflow is None:
                raise ValueError(
                    "Clearing schedule temperature requires airflow and no temperature"
                )
            return {"airflow_pct": airflow, "temp_c": None, "temp_unset": True}
    else:
        airflow, temperature = value, None
    if temperature is None and isinstance(current, dict):
        temperature = current.get("temp_c")
        if temperature is None and airflow is not None and current.get("airflow_pct") is not None:
            # The fresh device word has TT=0 (no temperature); keep it that way.
            return {"airflow_pct": airflow, "temp_c": None, "temp_unset": True}
    if temperature is None or airflow is None:
        raise ValueError("AATT requires an airflow and a known temperature; refusing to invent 0 C")
    return {"airflow_pct": airflow, "temp_c": temperature}
