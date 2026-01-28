"""Register address constants for ThesslaGreen Modbus integration."""

# Register address constants are defined as decimal integers per manufacturer spec.

REG_MIN_PERCENT = 276  # 0x0114
REG_MAX_PERCENT = 277  # 0x0115
REG_ON_OFF_PANEL_MODE = 4387  # 0x1123

# Temporary airflow write block (mode/value/flag)
REG_TEMPORARY_FLOW_START = 4400  # 0x1130
REG_TEMPORARY_FLOW_MODE = 4400  # 0x1130
REG_TEMPORARY_FLOW_VALUE = 4401  # 0x1131
REG_TEMPORARY_FLOW_FLAG = 4402  # 0x1132

# Temporary temperature write block (mode/value/flag)
REG_TEMPORARY_TEMP_START = 4403  # 0x1133
REG_TEMPORARY_TEMP_MODE = 4403  # 0x1133
REG_TEMPORARY_TEMP_VALUE = 4404  # 0x1134
REG_TEMPORARY_TEMP_FLAG = 4405  # 0x1135

