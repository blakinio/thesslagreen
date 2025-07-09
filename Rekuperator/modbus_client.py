from pymodbus.client import ModbusTcpClient

REGISTER_MAP = [
    # Przykładowe rejestry, rozwiń wg własnej dokumentacji!
    {"name": "outside_temperature", "register": 16, "unit": "°C", "type": "input", "scale": 0.1},
    {"name": "supply_temperature", "register": 17, "unit": "°C", "type": "input", "scale": 0.1},
    {"name": "exhaust_temperature", "register": 18, "unit": "°C", "type": "input", "scale": 0.1},
    {"name": "fpx_temperature", "register": 19, "unit": "°C", "type": "input", "scale": 0.1},
    {"name": "bypass", "register": 4320, "unit": None, "type": "holding", "scale": 1},
    {"name": "alarm", "register": 8192, "unit": None, "type": "holding", "scale": 1},
    # Dodaj wszystkie kolejne z PDF...
]

class ThesslaGreenClient:
    def __init__(self, host, port, slave_id):
        self.client = ModbusTcpClient(host, port=port)
        self.slave_id = slave_id

    def read_all(self):
        result = {}
        for reg in REGISTER_MAP:
            addr = reg["register"]
            scale = reg["scale"]
            if reg["type"] == "input":
                rr = self.client.read_input_registers(addr, 1, unit=self.slave_id)
            else:
                rr = self.client.read_holding_registers(addr, 1, unit=self.slave_id)
            if rr.isError():
                result[reg["name"]] = None
            else:
                result[reg["name"]] = rr.registers[0] * scale
        return result

    def write_register(self, addr, value):
        return self.client.write_register(addr, value, unit=self.slave_id)
