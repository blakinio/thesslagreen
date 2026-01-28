"""Register address constants for ThesslaGreen Modbus integration."""

# Register address constants are defined as decimal integers per manufacturer spec.

REG_MIN_PERCENT = 276  # 0114 hex
REG_MAX_PERCENT = 277  # 0115 hex
REG_ON_OFF_PANEL_MODE = 4387  # 1123 hex

# Temporary airflow write block (mode/value/flag)
REG_TEMPORARY_FLOW_START = 4400  # 1130 hex
REG_TEMPORARY_FLOW_MODE = 4400  # 1130 hex
REG_TEMPORARY_FLOW_VALUE = 4401  # 1131 hex
REG_TEMPORARY_FLOW_FLAG = 4402  # 1132 hex

# Temporary temperature write block (mode/value/flag)
REG_TEMPORARY_TEMP_START = 4403  # 1133 hex
REG_TEMPORARY_TEMP_MODE = 4403  # 1133 hex
REG_TEMPORARY_TEMP_VALUE = 4404  # 1134 hex
REG_TEMPORARY_TEMP_FLAG = 4405  # 1135 hex
