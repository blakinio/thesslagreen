# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/blakinio/thesslagreen.svg)](https://github.com/blakinio/thesslagreen/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.1.0%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org/)

## ✨ Complete ThesslaGreen AirPack integration for Home Assistant

The most complete integration for ThesslaGreen AirPack heat recovery units over Modbus TCP/RTU. Supports **all 200+ registers** from documentation [MODBUS_USER_AirPack_Home_08.2021.01](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_Home_08.2021.01.pdf) without exception.
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
- ✅ **Modbus TCP protocol** – native connection, fully supported
- ✅ **Modbus RTU (RS485) / USB** – supported serial connection
- ✅ **Firmware v3.x – v5.x** with automatic detection

### Modbus modes and requirements
- **Update schedule:** 30 s by default, configurable 10–300 s; avoid going below 15 s to prevent device overload.
- **Register coverage:** full support for Holding/Input/Coils/Discrete Input registers per vendor documentation.
- **Request batching:** reads are grouped into blocks (max 16 registers; 16 by default) to minimize network traffic.
- **Protocol limit:** max 16 registers per request (integration transport safety limit).
- **Fan/airflow range:** 0–150% (min/max read from the device).
- **Temperature values:** 32768 means invalid data and is mapped to `unknown`.
- **Limitations:** multiple simultaneous Modbus TCP connections to one controller may cause timeouts; keep only one active connection (Home Assistant).
- **TCP prerequisites:** port 502 open, static IP, device ID 10 (auto fallback to 1 and 247), no firewall/IPS between HA and the unit.
- **RTU/USB:** connect via `/dev/ttyUSBx` with 19200 8N1 (or per your installation).

### Home Assistant
- ✅ **Minimum Home Assistant version: 2026.1.0**
- ✅ **Tested with: 2026.1.x**
- ✅ **pymodbus 3.5.0+** – latest Modbus library
- ✅ **Python 3.12+** – modern standards
- ✅ **Standard AsyncModbusTcpClient** – no custom Modbus client required

## 🚀 Installation

### HACS (recommended)

1. **Add the custom repository in HACS**:
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/blakinio/thesslagreen`
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
git clone https://github.com/blakinio/thesslagreen.git
cp -r thesslagreen/custom_components/thessla_green_modbus custom_components/
```

## ⚙️ Step-by-step configuration

### 0. Preparation
1. Verify Home Assistant can reach the unit (ping the IP address) and connect to port 502.
2. Assign a static IP to the unit (DHCP reservation or manual) to avoid connection drops.
3. If you use RTU/USB, note the port (`/dev/ttyUSB0`), speed (e.g. 19200) and 8N1 parameters.

### 1. Enable Modbus on the unit
- **Modbus TCP**: Menu → Communication → Modbus TCP → Enable **YES**, Port **502**, Device ID **10**
- **Modbus RTU**: Menu → Communication → Modbus RTU → Select RS485 port, set baud rate (e.g. 19200), parity and stop bits

### 2. Add the integration in Home Assistant
1. **Settings** → **Devices & Services** → **+ ADD INTEGRATION**
2. Search for **"ThesslaGreen Modbus"**
3. Provide connection details:
   - Select **Connection type**: `Modbus TCP` or `Modbus RTU`
   - **Modbus TCP**: IP address (e.g. 192.168.1.100), port 502, Device ID 10 (the integration will also try 1 and 247)
   - **Modbus RTU/USB**: serial port (e.g. `/dev/ttyUSB0`), baud (e.g. 19200), parity and stop bits
4. Submit the form – the integration will auto-scan registers
5. After the scan completes click **ADD** and open the created device

### 3. Verify entities and status
1. In **Settings → Devices & Services** open **ThesslaGreen Modbus**.
2. Check entities (Climate, Fan, sensors and diagnostics).
3. In entity attributes (**Developer Tools → States**) you will see `last_updated` and `operating_mode` confirming the last successful read.

### 4. Advanced options
- **Scan interval**: 10‑300s (default 30s)
- **Timeout**: 5‑60s (default 10s)
- **Retry**: 1‑5 attempts (default 3)
- **Full register list**: Skip scanning (may cause errors)

> 🔎 The scanner probes many registers, including configuration blocks or
> multi-register values that do not map directly to Home Assistant entities.
> By default the integration only exposes addresses defined in
> [`mappings/__init__.py`](custom_components/thessla_green_modbus/mappings/__init__.py).
> Enabling the **Full register list** option (`force_full_register_list`)
> creates entities for every discovered register, but some may contain
> partial values or internal configuration. Use this option with care.
> [More details](docs/register_scanning.md).

### Auto-scan process
During setup the `ThesslaGreenDeviceScanner` module from
`custom_components/thessla_green_modbus/scanner/core.py` invokes
`scan_device()`. This method opens a Modbus connection, scans available
registers and device capabilities, then closes the client. The results
populate `available_registers`, from which the coordinator creates only
entities supported by the device. After firmware updates run the scan
again (e.g. remove and re-add the integration) to refresh
`available_registers`.

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

## 🔧 Diagnostics and logging

### Enable extended logs
Add to `configuration.yaml` and restart Home Assistant:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
    homeassistant.components.modbus: debug  # optional raw Modbus communication
```

Logs are visible in **Settings → System → Logs** and the `home-assistant.log` file. Debug level shows raw and processed register values, unavailable sensors, out-of-range values and connection errors.

### View last read and error counters
- **Entity attributes:** in **Developer Tools → States** open any integration entity; the `last_updated` attribute marks the last successful poll.
- **Device diagnostics:** **Settings → Devices & Services → ThesslaGreen Modbus → ⋮ → Download diagnostics** to see `last_successful_update`, `successful_reads`/`failed_reads`, `last_error` and response-time statistics.
- **`get_diagnostic_info` service:** call `thessla_green_modbus.get_diagnostic_info` from **Developer Tools → Services** to retrieve full diagnostics (device identity, available registers, error history).

## ❔ FAQ

**Connection lost (timeout/connection errors)**
- Confirm port 502 is reachable (firewall/router) and the unit keeps the same IP address.
- Increase the scan interval to 45–60 s in integration options to reduce load (avoid going below 15 s).
- Ensure no other tools keep a parallel Modbus session.

**Re‑auth / IP change**
- Go to **Settings → Devices & Services → ThesslaGreen Modbus → Configure** and replace IP/port/ID (no dedicated login).
- If switching TCP ↔ RTU, remove the integration and add it again after changing the transport on the unit panel.

**Changing the refresh interval**
- Open **Settings → Devices & Services → ThesslaGreen Modbus → Configure → Advanced options**.
- Set **Scan interval** (10–300 s); recommended 30 s, minimum 15 s for stability.
- After saving wait for the next scan cycle to apply.

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
Skipping unsupported input registers 256-258 (exception code 2)
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
- 📖 [Full documentation](https://github.com/blakinio/thesslagreen/wiki)
- 🔧 [Advanced configuration](DEPLOYMENT.md)
- 🚀 [Quick Start Guide](QUICK_START.md)

### Support
- 🐛 [Report issues](https://github.com/blakinio/thesslagreen/issues)
- 💡 [Feature requests](https://github.com/blakinio/thesslagreen/discussions)
- 🤝 [Contributing](CONTRIBUTING.md)

### Validate translations
Ensure translation files contain valid JSON:

```bash
python -m json.tool custom_components/thessla_green_modbus/translations/*.json
```

### Changelog
See [CHANGELOG.md](CHANGELOG.md) for full history.

## JSON register definitions

The file `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
stores the complete register specification and is the single canonical source
of truth (the former `registers/` copy was removed). All tools in `tools/`
operate exclusively on this JSON format.

> **New:** Utility modules can now be imported without the `homeassistant`
> package installed. HA-specific imports are loaded only when the integration
> runs inside Home Assistant.

### File format

Each entry in the file is an object with fields:

```json
{
  "function": "holding",
  "address_dec": 4097,
  "access": "rw",
  "name": "mode",
  "description": "Tryb pracy",
  "description_en": "Work mode"
}
```

Optional properties: `enum`, `multiplier`, `resolution`, `min`, `max`.

### Adding new registers

1. Edit `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` and append a new object
   with the required fields (`function`, `address_dec`, `name`, `description`, `description_en`, `access`).
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
