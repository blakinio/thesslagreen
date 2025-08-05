# 🚀 Quick Start Guide - ThesslaGreen Modbus Integration

Get your ThesslaGreen AirPack connected to Home Assistant in just a few minutes!

## ⚡ 5-Minute Setup

### Step 1: Prerequisites Check ✅

Before starting, make sure you have:
- [ ] Home Assistant 2023.4.0 or newer
- [ ] ThesslaGreen AirPack with Modbus TCP enabled
- [ ] Network connection between HA and your AirPack
- [ ] HACS installed (recommended) or manual installation capability

### Step 2: Enable Modbus on Your AirPack 🔧

1. **Access your AirPack panel**
2. **Navigate to:** Menu → Communication → Modbus TCP
3. **Set:** Enable = YES, Port = 502, Slave ID = 10
4. **Note your AirPack's IP address** (e.g., 192.168.1.100)

### Step 3: Install the Integration 📦

#### Option A: HACS (Recommended)
```
1. Open HACS → Integrations
2. Click ⋮ → Custom repositories  
3. Add: https://github.com/thesslagreen/thessla-green-modbus-ha
4. Category: Integration
5. Click ADD → Install "ThesslaGreen Modbus"
6. Restart Home Assistant
```

#### Option B: Manual Installation
```bash
1. Download latest release from GitHub
2. Extract to: config/custom_components/thessla_green_modbus/
3. Restart Home Assistant
```

### Step 4: Add Integration ➕

1. **Go to:** Settings → Devices & Services
2. **Click:** + ADD INTEGRATION  
3. **Search:** "ThesslaGreen Modbus"
4. **Enter:**
   - **IP Address:** 192.168.1.100 (your AirPack IP)
   - **Port:** 502
   - **Slave ID:** 10 (will auto-detect if wrong)
5. **Click:** SUBMIT

🎉 **Done!** Your AirPack should now be connected.

---

## 📊 What You'll Get

After successful setup, you'll see these entities in Home Assistant:

### 🌡️ **Climate Control**
- `climate.thessla_rekuperator` - Main climate entity with preset modes

### 🌡️ **Temperature Sensors**
- Outside temperature
- Supply air temperature  
- Exhaust air temperature
- FPX temperature (if available)

### 💨 **Ventilation Control**
- `fan.thessla_wentylator` - Fan speed control
- `select.thessla_mode` - Operating mode (Auto/Manual/Temporary)
- `number.thessla_air_flow_rate_manual` - Intensity control

### ⚙️ **System Status**
- `binary_sensor.thessla_device_status_smart` - Device on/off status
- Power supply status
- Constant Flow status (if available)

### 🔧 **Advanced Features** (if available)
- GWC system controls
- Bypass controls  
- Special functions (OKAP, KOMINEK, WIETRZENIE)

---

## 🎮 Quick Actions

### Basic Climate Control
```yaml
# Turn on with eco mode
service: climate.set_preset_mode
target:
  entity_id: climate.thessla_rekuperator
data:
  preset_mode: "eco"

# Set to boost mode
service: climate.set_preset_mode  
target:
  entity_id: climate.thessla_rekuperator
data:
  preset_mode: "boost"
```

### Manual Intensity Control
```yaml
# Set 60% intensity
service: number.set_value
target:
  entity_id: number.thessla_air_flow_rate_manual
data:
  value: 60
```

### Special Functions
```yaml
# Enable kitchen hood mode
service: select.select_option
target:
  entity_id: select.thessla_special_function
data:
  option: "OKAP"
```

---

## 📱 Dashboard Quick Setup

### Simple Control Card
```yaml
type: entities
entities:
  - climate.thessla_rekuperator
  - sensor.thessla_outside_temperature
  - sensor.thessla_supply_temperature
  - select.thessla_mode
title: ThesslaGreen Control
```

### Temperature History
```yaml
type: history-graph
entities:
  - sensor.thessla_outside_temperature
  - sensor.thessla_supply_temperature
  - sensor.thessla_exhaust_temperature
hours_to_show: 24
title: Temperature Trends
```

---

## 🔧 Troubleshooting Quick Fixes

### ❌ "Cannot connect to device"
**Solutions:**
1. **Check IP address** - Ping your AirPack: `ping 192.168.1.100`
2. **Check Modbus settings** - Ensure TCP is enabled, port 502
3. **Try different Slave ID** - Integration auto-detects 1, 10, 247
4. **Check firewall** - Ensure port 502 is open

### ❌ "No entities created"
**Solutions:**
1. **Wait 30 seconds** - Initial scan takes time
2. **Check logs** - Look for errors in HA logs
3. **Restart integration** - Remove and re-add integration
4. **Check device model** - Ensure your AirPack supports Modbus

### ❌ "Entities unavailable"
**Solutions:**
1. **Check network connection** - Device might have lost connection
2. **Restart AirPack** - Power cycle your unit
3. **Check entity states** - Some entities only appear when active

---

## ⚡ Performance Tips

### Optimize Update Speed
1. **Ethernet connection** - Use wired connection for best performance
2. **Stable IP** - Set static IP for your AirPack
3. **Close proximity** - Keep HA and AirPack on same network segment

### Reduce Network Load
- The integration is already optimized with batch reading
- Default 30-second updates are efficient for HVAC systems
- Avoid setting scan interval below 15 seconds

---

## 🎯 Next Steps

### 1. Create Automations
```yaml
# Example: Auto boost when cooking
automation:
  - alias: "Kitchen boost mode"
    trigger:
      - platform: state
        entity_id: binary_sensor.kitchen_motion
        to: 'on'
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.thessla_rekuperator
        data:
          preset_mode: "boost"
```

### 2. Add to Energy Dashboard
- Monitor power consumption estimates
- Track ventilation efficiency
- Compare seasonal performance

### 3. Advanced Configuration
- Set up schedules for different times of day
- Create scenes for different home modes
- Integrate with presence detection

---

## 📚 Learn More

- 📖 **[Full Documentation](README.md)** - Complete setup guide
- 🔧 **[Advanced Configuration](DEPLOYMENT.md)** - Detailed configuration options
- 🤝 **[Get Help](https://github.com/thesslagreen/thessla-green-modbus-ha/discussions)** - Community support
- 🐛 **[Report Issues](https://github.com/thesslagreen/thessla-green-modbus-ha/issues)** - Bug reports

---

**🎉 Congratulations!** Your ThesslaGreen AirPack is now smart home ready! 

Enjoy better air quality with intelligent automation! 🏠💨