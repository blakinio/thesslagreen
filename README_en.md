# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/thesslagreen/thessla-green-modbus-ha.svg)](https://github.com/thesslagreen/thessla-green-modbus-ha/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.7.1%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org/)

## ✨ Complete ThesslaGreen AirPack integration for Home Assistant

The most complete integration for ThesslaGreen AirPack heat recovery units over Modbus TCP/RTU. Supports **all 200+ registers** from documentation `MODBUS_USER_AirPack_Home_08.2021.01` without exception.
The integration works as a **hub** in Home Assistant.

### 🚀 Key features v2.1+

- **🔍 Smart device scanning** – automatically detects available features and registers
- **📱 Only active entities** – creates only entities that are really available
- **🏠 Full control of the unit** – all work modes, temperatures and air flows
- **📊 Complete monitoring** – all sensors, statuses, alarms and diagnostics
- **🔋 Energy estimation** – built-in power and total energy sensors
- **🌡️ Advanced Climate entity** – full HVAC control with preset modes and special modes
- **⚡ Every special function** – HOOD, FIREPLACE, VENTILATION, EMPTY HOUSE, BOOST
- **🌿 GWC and Bypass systems** – complete control of additional systems
- **📅 Weekly schedule** – full configuration of time programs
- **🛠️ 14 services** – complete API for automation and control, including full register scan
- **🔧 Diagnostics and logging** – detailed error and performance information
- **🌍 Multilingual support** – Polish and English

## 📋 Compatibility

### Devices
- ✅ **ThesslaGreen AirPack Home Series 4** – all models
- ✅ **AirPack Home 300v‑850h** (Energy+, Energy, Enthalpy)
- ✅ **Modbus TCP/RTU protocol** with auto detection
- ✅ **Firmware v3.x – v5.x** with automatic detection

### Home Assistant
- ✅ **Requires Home Assistant 2025.7.1+** — minimum version declared in `manifest.json` (the `homeassistant` package is not part of `requirements.txt`)
- ✅ **pymodbus 3.5.0+** – latest Modbus library
- ✅ **Python 3.12+** – modern standards
- ✅ **Standard AsyncModbusTcpClient** – no custom Modbus client required

## 🚀 Installation

### HACS (recommended)

1. **Add the custom repository in HACS**:
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/thesslagreen/thessla-green-modbus-ha`
   - Category: Integration
   - Click ADD
2. **Install the integration**:
   - Find "ThesslaGreen Modbus" in HACS
   - Click INSTALL
   - Restart Home Assistant

### Manual installation

```bash
# Copy files into your custom_components directory
cd /config
git clone https://github.com/thesslagreen/thessla-green-modbus-ha.git
cp -r thessla-green-modbus-ha/custom_components/thessla_green_modbus custom_components/
```

## ⚙️ Configuration

### 1. Enable Modbus TCP in the unit
- Menu → Communication → Modbus TCP
- Enable: **YES**
- Port: **502** (default)
- Device ID: **10** (default)

### 2. Add the integration in Home Assistant
1. **Settings** → **Devices & Services** → **+ ADD INTEGRATION**
2. Search for **"ThesslaGreen Modbus"**
3. Enter the data:
   - **IP Address**: unit IP (e.g. 192.168.1.100)
   - **Port**: 502
   - **Device ID**: 10
4. The integration will automatically scan the device
5. Click **ADD**

### 3. Advanced options
- **Scan interval**: 10‑300s (default 30s)
- **Timeout**: 5‑60s (default 10s)
- **Retry**: 1‑5 attempts (default 3)
- **Full register list**: Skip scanning (may cause errors)

> 🔎 The scanner probes many registers, including configuration blocks or
> multi-register values that do not map directly to Home Assistant entities.
> By default the integration only exposes addresses defined in
> [`entity_mappings.py`](custom_components/thessla_green_modbus/entity_mappings.py).
> Enabling the **Full register list** option (`force_full_register_list`)
> creates entities for every discovered register, but some may contain
> partial values or internal configuration. Use this option with care.
> [More details](docs/register_scanning.md).

## 📊 Available entities

### Sensors (50+ auto detected)
- **Temperatures**: outdoor, supply, exhaust, FPX, GWC, duct, ambient
- **Flows**: supply, exhaust, actual, min/max range
- **Pressures**: supply, exhaust, differential, alarms
- **Air quality**: CO₂, VOC, air quality index, humidity
- **Energy**: consumption, recovery, peak power, average, annual CO₂ reduction (kg)
- **System**: calculated efficiency, operating hours, filter status, errors
- **Diagnostics**: update time, data quality, statistics

### Binary sensors (40+ auto detected)
- **System status**: fan power, bypass, GWC, pumps
- **Modes**: summer/winter, auto/manual, special modes (boost, eco, away, sleep, fireplace, hood, party, bathroom, kitchen, summer, winter)
- **Inputs**: expansion, fire alarm, air quality sensor
- **Errors and alarms**: all codes S1‑S32 and E99‑E105
- **Protections**: thermal, anti freeze, overloads

### Controls (30+ auto detected)
- **Climate**: full HVAC control with preset modes
- **Switches**: all systems, modes and configuration
- **Numbers**: temperatures, intensities, times, alarm limits
- **Selects**: work modes, season mode, schedule, communication, language

## 🛠️ Services (14 complete services)

### Basic control
```yaml
# Set work mode
service: thessla_green_modbus.set_mode
data:
  mode: "auto"
  intensity: 70

# Activate special mode
...
    action:
      - service: thessla_green_modbus.set_mode
        data:
          mode: "auto"
          intensity: 60
      - service: thessla_green_modbus.set_temperature
        data:
          temperature: 20.0
          mode: "comfort"
```

### Error monitoring
The `sensor.thessla_error_codes` sensor aggregates both error codes (`E*`) and status codes (`S*`).
```yaml
automation:
  - alias: "Alarm on errors"
    trigger:
      - platform: state
        entity_id: binary_sensor.thessla_error_status
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 ThesslaGreen Error"
          message: >
            Ventilation system error detected!
            Error code: {{ states('sensor.thessla_error_codes') }}
      - service: light.turn_on
        target:
          entity_id: light.living_room_led
        data:
          rgb_color: [255, 0, 0]
          flash: "long"
```

## 🔧 Diagnostics and troubleshooting

### Diagnostic information
Use the `get_diagnostic_info` service to receive:
- Device information (firmware, serial, model)
- Integration performance stats
- Available registers and functions
- Communication error history

### Common problems

#### ❌ "Cannot connect"
1. Check IP and ping the device: `ping 192.168.1.100`
2. Ensure Modbus TCP is enabled (port 502)
3. Try different Device IDs (integration auto detects 1, 10, 247)
4. Check network firewall

#### ❌ "No entities"
1. Wait 30‑60 seconds for initial scanning
2. Check logs in **Settings** → **System** → **Logs**
3. Use the `rescan_device` service
4. If needed enable "Full register list"

#### ❌ "Entities unavailable"
1. Check network connection
2. Restart the unit (power off for 30s)
3. Check entity status in **Developer Tools**

### Debug logging
Add to `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.thessla_green_modbus: debug
    pymodbus: info
```

### "Skipping unsupported … registers" warnings
During scanning the integration tries many register ranges. If the unit
doesn't support a range, the logs show a warning like:

```
Skipping unsupported input registers 0x0100-0x0102 (exception code 2)
```

Modbus exception codes explain why the read failed:

- **2 – Illegal Data Address** – register range not implemented
- **3 – Illegal Data Value** – register exists but rejected the request (e.g. feature disabled)
- **4 – Slave Device Failure** – the device could not process the request

Warnings that only appear during the initial scan or for optional features
can usually be ignored. Persistent warnings for important registers may
indicate a configuration or firmware mismatch.

## 📋 Technical specification

### Supported registers
| Register type | Count | Coverage |
|---------------|-------|----------|
| Input Registers | 80+ | Sensors, status, diagnostics |
| Holding Registers | 150+ | Control, configuration, schedule |
| Coil Registers | 35+ | Output control, modes |
| Discrete Inputs | 30+ | Digital inputs, statuses |

### System functions
- ✅ **Basic control**: On/Off, modes, intensity
- ✅ **Temperature control**: manual and automatic
- ✅ **Special functions**: HOOD, FIREPLACE, VENTILATION, EMPTY HOUSE
- ✅ **Advanced systems**: GWC, Bypass, Constant flow
- ✅ **Diagnostics**: complete error and alarm reporting
- ✅ **Automation**: full integration with HA services
- ✅ **Monitoring**: energy efficiency (`calculated_efficiency` sensor) and runtime

### Performance
- **Optimized reads**: register grouping, 60% fewer Modbus calls
- **Auto scanning**: only available registers, no errors
- **Diagnostics**: detailed performance and error metrics
- **Stability**: retry logic, fallback reads, graceful degradation, and automatic
  skipping of unsupported registers

### Full register scan
The `thessla_green_modbus.scan_all_registers` service runs a complete register
scan (`full_register_scan=True`) and returns unknown addresses. This operation
may take several minutes and can heavily load the unit, so it should be used
only for diagnostic purposes.

## 🤝 Support and development

### Documentation
- 📖 [Full documentation](https://github.com/thesslagreen/thessla-green-modbus-ha/wiki)
- 🔧 [Advanced configuration](DEPLOYMENT.md)
- 🚀 [Quick Start Guide](QUICK_START.md)

### Support
- 🐛 [Report issues](https://github.com/thesslagreen/thessla-green-modbus-ha/issues)
- 💡 [Feature requests](https://github.com/thesslagreen/thessla-green-modbus-ha/discussions)
- 🤝 [Contributing](CONTRIBUTING.md)


### Updating `registers.py`
Whenever `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` changes, regenerate and
validate the Python module:

```bash
python tools/generate_registers.py
python tools/validate_registers.py  # optional consistency check
```

Commit the updated `custom_components/thessla_green_modbus/registers.py`
together with the modified JSON file.

### Validate translations
Ensure translation files contain valid JSON:

```bash
python -m json.tool custom_components/thessla_green_modbus/translations/*.json
```

### Changelog
See [CHANGELOG.md](CHANGELOG.md) for full history.

## JSON register definitions

The file `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` stores the complete
register specification and is the single source of truth. All tools in
`tools/` operate exclusively on this JSON format.

### File format

Each entry in the file is an object with fields:

```json
{
  "function": "holding",
  "address_hex": "0x1001",
  "address_dec": 4097,
  "access": "rw",
  "name": "mode",
  "description": "Work mode"
}
```

Optional properties: `enum`, `multiplier`, `resolution`, `min`, `max`.

### Adding new registers

1. Edit `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` and append a new object
   with the required fields.
2. Ensure addresses are unique and remain sorted.
3. Run the validation test:

```bash
pytest tests/test_register_loader.py
```

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgements

- **ThesslaGreen** for providing Modbus documentation
- **Home Assistant Community** for testing and feedback
- **pymodbus team** for the excellent Modbus library

---

**🎉 Enjoy smart ventilation with Home Assistant!** 🏠💨

