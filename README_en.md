# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/thesslagreen/thessla-green-modbus-ha.svg)](https://github.com/thesslagreen/thessla-green-modbus-ha/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.7.1%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org/)

## ✨ Complete ThesslaGreen AirPack integration for Home Assistant

The most complete integration for ThesslaGreen AirPack heat recovery units over Modbus TCP/RTU. Supports **all 200+ registers** from documentation `MODBUS_USER_AirPack_Home_08.2021.01` without exception.

### 🚀 Key features v2.1+

- **🔍 Smart device scanning** – automatically detects available features and registers
- **📱 Only active entities** – creates only entities that are really available
- **🏠 Full control of the unit** – all work modes, temperatures and air flows
- **📊 Complete monitoring** – all sensors, statuses, alarms and diagnostics
- **🌡️ Advanced Climate entity** – full HVAC control with preset modes and special modes
- **⚡ Every special function** – HOOD, FIREPLACE, VENTILATION, EMPTY HOUSE, BOOST
- **🌿 GWC and Bypass systems** – complete control of additional systems
- **📅 Weekly schedule** – full configuration of time programs
- **🛠️ 13 services** – complete API for automation and control
- **🔧 Diagnostics and logging** – detailed error and performance information
- **🌍 Multilingual support** – Polish and English

## 📋 Compatibility

### Devices
- ✅ **ThesslaGreen AirPack Home Serie 4** – all models
- ✅ **AirPack Home 300v‑850h** (Energy+, Energy, Enthalpy)
- ✅ **Modbus TCP/RTU protocol** with auto detection
- ✅ **Firmware v3.x – v5.x** with automatic detection

### Home Assistant
- ✅ **Requires Home Assistant 2025.7.1+** – minimum version declared in `manifest.json` (the `homeassistant` package is not part of `requirements.txt`)
- ✅ **pymodbus 3.5.0+** – latest Modbus library
- ✅ **Python 3.11+** – modern standards
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
- Slave ID: **10** (default)

### 2. Add the integration in Home Assistant
1. **Settings** → **Devices & Services** → **+ ADD INTEGRATION**
2. Search for **"ThesslaGreen Modbus"**
3. Enter the data:
   - **IP Address**: unit IP (e.g. 192.168.1.100)
   - **Port**: 502
   - **Slave ID**: 10
4. The integration will automatically scan the device
5. Click **ADD**

### 3. Advanced options
- **Scan interval**: 10‑300s (default 30s)
- **Timeout**: 5‑60s (default 10s)
- **Retry**: 1‑5 attempts (default 3)
- **Full register list**: Skip scanning (may cause errors)

## 📊 Available entities

### Sensors (50+ auto detected)
- **Temperatures**: outdoor, supply, exhaust, FPX, GWC, duct, ambient
- **Flows**: supply, exhaust, actual, min/max range
- **Pressures**: supply, exhaust, differential, alarms
- **Air quality**: CO₂, VOC, air quality index, humidity
- **Energy**: consumption, recovery, peak power, average, annual CO₂ reduction (kg)
- **System**: efficiency, operating hours, filter status, errors
- **Diagnostics**: update time, data quality, statistics

### Binary sensors (40+ auto detected)
- **System status**: fan power, bypass, GWC, pumps
- **Modes**: summer/winter, auto/manual, special modes
- **Inputs**: expansion, fire alarm, contractors, sensors
- **Errors and alarms**: all codes S1‑S32 and E99‑E105
- **Protections**: thermal, anti freeze, overloads

### Controls (30+ auto detected)
- **Climate**: full HVAC control with preset modes
- **Switches**: all systems, modes and configuration
- **Numbers**: temperatures, intensities, times, alarm limits
- **Selects**: work modes, schedule, communication, language

## 🛠️ Services (13 complete services)

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
            Error code: {{ states('sensor.thessla_error_code') }}
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
3. Try different Slave IDs (integration auto detects 1, 10, 247)
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
- ✅ **Monitoring**: energy efficiency and runtime

### Performance
- **Optimized reads**: register grouping, 60% fewer Modbus calls
- **Auto scanning**: only available registers, no errors
- **Diagnostics**: detailed performance and error metrics
- **Stability**: retry logic, fallback reads, graceful degradation

## 🤝 Support and development

### Documentation
- 📖 [Full documentation](https://github.com/thesslagreen/thessla-green-modbus-ha/wiki)
- 🔧 [Advanced configuration](DEPLOYMENT.md)
- 🚀 [Quick Start Guide](QUICK_START.md)

### Support
- 🐛 [Report issues](https://github.com/thesslagreen/thessla-green-modbus-ha/issues)
- 💡 [Feature requests](https://github.com/thesslagreen/thessla-green-modbus-ha/discussions)
- 🤝 [Contributing](CONTRIBUTING.md)

### Changelog
See [CHANGELOG.md](CHANGELOG.md) for full history.

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgements

- **ThesslaGreen** for providing Modbus documentation
- **Home Assistant Community** for testing and feedback
- **pymodbus team** for the excellent Modbus library

---

**🎉 Enjoy smart ventilation with Home Assistant!** 🏠💨
