# TeslaGreen Modbus Integration dla Home Assistant

Kompletna integracja Home Assistant dla rekuperatorów TeslaGreen z komunikacją Modbus TCP.

## Funkcje

- 🌡️ **Monitorowanie temperatury** - 4 czujniki temperatury (nawiew, wyciąg, zewnętrzna, wywiew)
- 🌬️ **Kontrola wentylacji** - Sterowanie prędkością wentylatorów i trybami pracy
- 🏠 **Kontrola klimatu** - Pełna integracja z systemem klimatyzacji Home Assistant
- 📊 **Jakość powietrza** - Monitorowanie CO2, wilgotności i indeksu jakości powietrza
- 🔄 **Bypass letni** - Kontrola bypass'u letnego
- ⚠️ **Alarmy i status** - Monitorowanie stanu systemu i filtrów
- 🔧 **Usługi niestandardowe** - Dodatkowe usługi do zaawansowanego sterowania

## Wymagania

- Home Assistant 2025.7+
- Urządzenie TeslaGreen z interfejsem Modbus TCP
- Python 3.11+
- pymodbus >= 3.0.0

## Instalacja

### Metoda 1: HACS (Rekomendowana)

1. Otwórz HACS w Home Assistant
2. Przejdź do "Integrations"
3. Kliknij menu (⋮) i wybierz "Custom repositories"
4. Dodaj URL: `https://github.com/yourusername/thessla_green_modbus`
5. Wybierz kategorię "Integration"
6. Kliknij "Add"
7. Znajdź "TeslaGreen Modbus" i kliknij "Install"

### Metoda 2: Instalacja manualna

1. Skopiuj katalog `custom_components/thessla_green_modbus` do katalogu `config/custom_components/` w Home Assistant
2. Uruchom ponownie Home Assistant
3. Przejdź do Configuration > Integrations
4. Kliknij "Add Integration" i wyszukaj "TeslaGreen Modbus"

## Konfiguracja

1. Po instalacji przejdź do **Configuration** > **Integrations**
2. Kliknij **"Add Integration"** i wyszukaj **"TeslaGreen Modbus"**
3. Wprowadź dane połączenia:
   - **IP Address**: Adres IP urządzenia TeslaGreen
   - **Port**: Port Modbus (domyślnie 502)
   - **Slave ID**: ID urządzenia Modbus (domyślnie 1)
4. Kliknij **"Submit"**

## Dostępne encje

### Sensory (sensor)
- `sensor.thessla_green_temp_supply` - Temperatura powietrza doprowadzanego
- `sensor.thessla_green_temp_extract` - Temperatura powietrza wyciąganego
- `sensor.thessla_green_temp_outdoor` - Temperatura zewnętrzna
- `sensor.thessla_green_temp_exhaust` - Temperatura powietrza wywiewanego
- `sensor.thessla_green_fan_supply_speed` - Prędkość wentylatora nawiewu
- `sensor.thessla_green_fan_extract_speed` - Prędkość wentylatora wyciągu
- `sensor.thessla_green_co2_level` - Poziom CO2
- `sensor.thessla_green_humidity` - Wilgotność
- `sensor.thessla_green_air_quality_index` - Indeks jakości powietrza

### Klimatyzacja (climate)
- `climate.thessla_green_rekuperator` - Główna kontrola klimatu

### Wentylator (fan)
- `fan.thessla_green_wentylator` - Kontrola wentylatorów

### Przełączniki (switch)
- `switch.thessla_green_bypass_control` - Bypass letni

### Kontrola liczbowa (number)
- `number.thessla_green_target_temperature` - Temperatura docelowa
- `number.thessla_green_fan_speed_setting` - Prędkość wentylatorów

### Wybór opcji (select)
- `select.thessla_green_mode_selection` - Tryb pracy

### Sensory binarne (binary_sensor)
- `binary_sensor.thessla_green_system_status` - Status systemu
- `binary_sensor.thessla_green_filter_status` - Stan filtra
- `binary_sensor.thessla_green_bypass_status` - Status bypass

## Usługi

### thessla_green_modbus.set_mode
Ustawia tryb pracy rekuperatora.

```yaml
service: thessla_green_modbus.set_mode
target:
  entity_id: climate.thessla_green_rekuperator
data:
  mode: "auto"  # auto, night, boost, away
```

### thessla_green_modbus.set_fan_speed
Ustawia prędkość wentylatorów.

```yaml
service: thessla_green_modbus.set_fan_speed
target:
  entity_id: fan.thessla_green_wentylator
data:
  percentage: 75
```

## Przykładowa automatyzacja

```yaml
automation:
  - alias: "TeslaGreen - Tryb nocny"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_green_mode_selection
        data:
          option: "Nocny"

  - alias: "TeslaGreen - Boost przy wysokim CO2"
    trigger:
      platform: numeric_state
      entity_id: sensor.thessla_green_co2_level
      above: 1000
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_green_mode_selection
        data:
          option: "Boost"
```

## Troubleshooting

### Nie można połączyć się z urządzeniem
1. Sprawdź czy urządzenie TeslaGreen jest podłączone do sieci
2. Sprawdź adres IP i port Modbus
3. Sprawdź czy Modbus TCP jest włączony w urządzeniu
4. Sprawdź logi Home Assistant w Configuration > Logs

### Brak danych z sensorów
1. Sprawdź połączenie sieciowe
2. Sprawdź czy Slave ID jest prawidłowy
3. Sprawdź rejestry Modbus w dokumentacji urządzenia

### Debug
Włącz logowanie debug w `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.thessla_green_modbus: debug
```

##
        
    
