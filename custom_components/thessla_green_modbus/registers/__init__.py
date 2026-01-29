"""Helpers and constants for ThesslaGreen register definitions."""

# Register address constants are defined as decimal integers per manufacturer spec.

REG_MIN_PERCENT = 276
REG_MAX_PERCENT = 277
REG_ON_OFF_PANEL_MODE = 4387

# Temporary airflow write block (mode/value/flag)
REG_TEMPORARY_FLOW_START = 4400
REG_TEMPORARY_FLOW_MODE = 4400
REG_TEMPORARY_FLOW_VALUE = 4401
REG_TEMPORARY_FLOW_FLAG = 4402

# Temporary temperature write block (mode/value/flag)
REG_TEMPORARY_TEMP_START = 4403
REG_TEMPORARY_TEMP_MODE = 4403
REG_TEMPORARY_TEMP_VALUE = 4404
REG_TEMPORARY_TEMP_FLAG = 4405

__all__ = [
    "REG_MAX_PERCENT",
    "REG_MIN_PERCENT",
    "REG_ON_OFF_PANEL_MODE",
    "REG_TEMPORARY_FLOW_FLAG",
    "REG_TEMPORARY_FLOW_MODE",
    "REG_TEMPORARY_FLOW_START",
    "REG_TEMPORARY_FLOW_VALUE",
    "REG_TEMPORARY_TEMP_FLAG",
    "REG_TEMPORARY_TEMP_MODE",
    "REG_TEMPORARY_TEMP_START",
    "REG_TEMPORARY_TEMP_VALUE",
]
