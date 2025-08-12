# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/thesslagreen/thessla-green-modbus-ha.svg)](https://github.com/thesslagreen/thessla-green-modbus-ha/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.7.1%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org/)

## ✨ Kompletna integracja ThesslaGreen AirPack z Home Assistant

Najkompletniejsza integracja dla rekuperatorów ThesslaGreen AirPack z protokołem Modbus TCP/RTU. Obsługuje **wszystkie 200+ rejestrów** z dokumentacji MODBUS_USER_AirPack_Home_08.2021.01 bez wyjątku.

### 🚀 Kluczowe funkcje v2.1+

- **🔍 Inteligentne skanowanie urządzenia** - automatycznie wykrywa dostępne funkcje i rejestry
- **📱 Tylko aktywne encje** - tworzy tylko te encje, które są rzeczywiście dostępne
- **🏠 Kompletna kontrola rekuperatora** - wszystkie tryby pracy, temperatury, przepływy
- **📊 Pełny monitoring** - wszystkie czujniki, statusy, alarmy, diagnostyka
- **🌡️ Zaawansowana encja Climate** - pełna kontrola z preset modes i trybami specjalnymi
- **⚡ Wszystkie funkcje specjalne** - OKAP, KOMINEK, WIETRZENIE, PUSTY DOM, BOOST
- **🌿 Systemy GWC i Bypass** - kompletna kontrola systemów dodatkowych
- **📅 Harmonogram tygodniowy** - pełna konfiguracja programów czasowych
- **🛠️ 13 serwisów** - kompletne API do automatyzacji i kontroli
- **🔧 Diagnostyka i logowanie** - szczegółowe informacje o błędach i wydajności
- **🌍 Wsparcie wielojęzyczne** - polski i angielski

## 📋 Kompatybilność

### Urządzenia
- ✅ **ThesslaGreen AirPack Home Series 4** - wszystkie modele
- ✅ **AirPack Home 300v-850h** (Energy+, Energy, Enthalpy)
- ✅ **Protokół Modbus TCP/RTU** z auto-detekcją
- ✅ **Firmware v3.x - v5.x** z automatyczną detekcją

### Home Assistant
- ✅ **Wymagany Home Assistant 2025.7.1+** – minimalna wersja określona w `manifest.json` (pakiet `homeassistant` nie jest częścią `requirements.txt`)
- ✅ **pymodbus 3.5.0+** - najnowsza biblioteka Modbus
- ✅ **Python 3.12+** - nowoczesne standardy
- ✅ **Standardowy AsyncModbusTcpClient** – brak potrzeby własnego klienta Modbus

## 🚀 Instalacja

### HACS (Rekomendowane)

1. **Dodaj repozytorium custom w HACS:**
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/thesslagreen/thessla-green-modbus-ha`
   - Category: Integration
   - Kliknij ADD

2. **Zainstaluj integrację:**
   - Znajdź "ThesslaGreen Modbus" w HACS
   - Kliknij INSTALL
   - Zrestartuj Home Assistant

### Instalacja manualna

```bash
# Skopiuj pliki do katalogu custom_components
cd /config
git clone https://github.com/thesslagreen/thessla-green-modbus-ha.git
cp -r thessla-green-modbus-ha/custom_components/thessla_green_modbus custom_components/
```

## ⚙️ Konfiguracja

### 1. Włącz Modbus TCP w rekuperatorze
- Menu → Komunikacja → Modbus TCP
- Włącz: **TAK**
- Port: **502** (domyślny)
- Slave ID: **10** (domyślny)

### 2. Dodaj integrację w Home Assistant
1. **Ustawienia** → **Integracje** → **+ DODAJ INTEGRACJĘ**
2. Wyszukaj **"ThesslaGreen Modbus"**
3. Wprowadź dane:
   - **IP Address**: IP rekuperatora (np. 192.168.1.100)
   - **Port**: 502
   - **Slave ID**: 10
4. Integracja automatycznie przeskanuje urządzenie
5. Kliknij **DODAJ**

### 3. Opcje zaawansowane
- **Interwał skanowania**: 10-300s (domyślnie 30s)
- **Timeout**: 5-60s (domyślnie 10s)
- **Retry**: 1-5 prób (domyślnie 3)
- **Pełna lista rejestrów**: Pomiń skanowanie (może powodować błędy)

## 📊 Dostępne encje

### Sensory (50+ automatycznie wykrywanych)
- **Temperatury**: Zewnętrzna, nawiew, wywiew, FPX, GWC, kanałowa, otoczenia
- **Przepływy**: Nawiew, wywiew, rzeczywisty, min/max zakresy
- **Ciśnienia**: Nawiew, wywiew, różnicowe, alarmy
- **Jakość powietrza**: CO2, VOC, indeks jakości, wilgotność
- **Energie**: Zużycie, odzysk, moc szczytowa, średnia, roczna redukcja CO2 (kg)
- **System**: Sprawność, godziny pracy, status filtrów, błędy
- **Diagnostyka**: Czas aktualizacji, jakość danych, statystyki

### Sensory binarne (40+ automatycznie wykrywanych)
- **Status systemu**: Zasilanie wentylatorów, bypass, GWC, pompy
- **Tryby**: Letni/zimowy, auto/manual, tryby specjalne (boost, eco, away, sleep, fireplace, hood, party, bathroom, kitchen, summer, winter)
- **Wejścia**: Expansion, alarm pożarowy, kontaktrony, czujniki
- **Błędy i alarmy**: Wszystkie kody S1-S32 i E99-E105
- **Zabezpieczenia**: Termiczne, przeciwmrozowe, przeciążenia

### Kontrolki (30+ automatycznie wykrywanych)
- **Climate**: Kompletna kontrola HVAC z preset modes
- **Switches**: Wszystkie systemy, tryby, konfiguracja
- **Numbers**: Temperatury, intensywności, czasy, limity alarmów
- **Selects**: Tryby pracy, harmonogram, komunikacja, język

## 🛠️ Serwisy (13 kompletnych serwisów)

### Podstawowe sterowanie
```yaml
# Ustaw tryb pracy
service: thessla_green_modbus.set_mode
data:
  mode: "auto"
  intensity: 70

# Aktywuj tryb specjalny
service: thessla_green_modbus.set_special_mode
data:
  special_mode: "hood"
  intensity: 100
  duration: 30

# Ustaw temperaturę
service: thessla_green_modbus.set_temperature
data:
  temperature: 22.5
  mode: "comfort"
```

### Kontrola wentylacji
```yaml
# Ustaw prędkość wentylatorów
service: thessla_green_modbus.set_fan_speed
data:
  supply_speed: 80
  exhaust_speed: 75
  balance: 5

# Steruj bypass
service: thessla_green_modbus.control_bypass
data:
  mode: "open"

# Steruj GWC
service: thessla_green_modbus.control_gwc
data:
  mode: "auto"
```

### Harmonogram i konserwacja
```yaml
# Ustaw harmonogram
service: thessla_green_modbus.set_schedule
data:
  day: "mon"
  period: 1
  start_time: "06:00"
  end_time: "08:00"
  intensity: 80
  temperature: 21.0

# Resetuj alarmy
service: thessla_green_modbus.reset_alarms
data:
  alarm_type: "all"

# Przeskanuj urządzenie
service: thessla_green_modbus.rescan_device
```

### Diagnostyka i kopia zapasowa
```yaml
# Pobierz informacje diagnostyczne
service: thessla_green_modbus.get_diagnostic_info

# Kopia zapasowa ustawień
service: thessla_green_modbus.backup_settings
data:
  include_schedule: true
  include_alarms: true

# Kalibracja czujników
service: thessla_green_modbus.calibrate_sensors
data:
  outside_offset: -0.5
  supply_offset: 0.3
```

## 📈 Przykłady automatyzacji

### Auto boost podczas gotowania
```yaml
automation:
  - alias: "Kuchnia - tryb HOOD"
    trigger:
      - platform: state
        entity_id: binary_sensor.kuchnia_ruch
        to: "on"
    action:
      - service: thessla_green_modbus.set_special_mode
        data:
          special_mode: "hood"
          intensity: 120
          duration: 45
```

### Harmonogram weekendowy
```yaml
automation:
  - alias: "Weekend - tryb ekonomiczny"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: time
        weekday:
          - sat
          - sun
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

### Monitoring błędów
```yaml
automation:
  - alias: "Alarm przy błędach"
    trigger:
      - platform: state
        entity_id: binary_sensor.thessla_error_status
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 ThesslaGreen Error"
          message: >
            Wykryto błąd systemu wentylacji!
            Kod błędu: {{ states('sensor.thessla_error_code') }}
      - service: light.turn_on
        target:
          entity_id: light.salon_led
        data:
          rgb_color: [255, 0, 0]
          flash: "long"
```

## 🔧 Diagnostyka i rozwiązywanie problemów

### Informacje diagnostyczne
Użyj serwisu `get_diagnostic_info` aby uzyskać:
- Informacje o urządzeniu (firmware, serial, model)
- Statystyki wydajności integracji
- Dostępne rejestry i funkcje
- Historię błędów komunikacji

### Typowe problemy

#### ❌ "Nie można połączyć"
1. Sprawdź IP i ping do urządzenia: `ping 192.168.1.100`
2. Upewnij się, że Modbus TCP jest włączony (port 502)
3. Spróbuj różnych Slave ID (integracja auto-wykrywa 1, 10, 247)
4. Sprawdź zaporę sieciową

#### ❌ "Brak encji"
1. Poczekaj 30-60 sekund na początkowe skanowanie
2. Sprawdź logi w **Ustawienia** → **System** → **Logi**
3. Użyj serwisu `rescan_device`
4. W razie potrzeby włącz opcję "Pełna lista rejestrów"

#### ❌ "Encje niedostępne"
1. Sprawdź połączenie sieciowe
2. Restart rekuperatora (wyłącz zasilanie na 30s)
3. Sprawdź status encji w **Narzędzia programistyczne**

### Logowanie debugowe
Dodaj do `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.thessla_green_modbus: debug
    pymodbus: info
```

## 📋 Specyfikacja techniczna

### Obsługiwane rejestry
| Typ rejestru | Liczba | Pokrycie |
|--------------|--------|----------|
| Input Registers | 80+ | Czujniki, status, diagnostyka |
| Holding Registers | 150+ | Kontrola, konfiguracja, harmonogram |
| Coil Registers | 35+ | Wyjścia sterujące, tryby |
| Discrete Inputs | 30+ | Wejścia cyfrowe, statusy |

### Funkcje systemowe
- ✅ **Kontrola podstawowa**: On/Off, tryby, intensywność
- ✅ **Kontrola temperatury**: Manualna i automatyczna
- ✅ **Funkcje specjalne**: OKAP, KOMINEK, WIETRZENIE, PUSTY DOM
- ✅ **Systemy zaawansowane**: GWC, Bypass, Stały przepływ
- ✅ **Diagnostyka**: Kompletne raportowanie błędów i alarmów
- ✅ **Automatyzacja**: Pełna integracja z serwisami HA
- ✅ **Monitoring**: Wydajność energetyczna i czas pracy

### Wydajność
- **Optymalizowane odczyty**: Grupowanie rejestrów, 60% mniej wywołań Modbus
- **Auto-skanowanie**: Tylko dostępne rejestry, brak błędów
- **Diagnostyka**: Szczegółowe metryki wydajności i błędów
- **Stabilność**: Retry logic, fallback reads, graceful degradation

## 🤝 Wsparcie i rozwój

### Dokumentacja
- 📖 [Pełna dokumentacja](https://github.com/thesslagreen/thessla-green-modbus-ha/wiki)
- 🔧 [Konfiguracja zaawansowana](DEPLOYMENT.md)
- 🚀 [Quick Start Guide](QUICK_START.md)

### Wsparcie
- 🐛 [Zgłaszanie błędów](https://github.com/thesslagreen/thessla-green-modbus-ha/issues)
- 💡 [Propozycje funkcji](https://github.com/thesslagreen/thessla-green-modbus-ha/discussions)
- 🤝 [Contributing](CONTRIBUTING.md)

### Changelog
Zobacz [CHANGELOG.md](CHANGELOG.md) dla pełnej historii zmian.

## 📄 Licencja

MIT License - Zobacz [LICENSE](LICENSE) dla szczegółów.

## 🙏 Podziękowania

- **ThesslaGreen** za udostępnienie dokumentacji Modbus
- **Społeczność Home Assistant** za testy i feedback
- **Zespół pymodbus** za doskonałą bibliotekę Modbus

---

**🎉 Ciesz się inteligentną wentylacją z Home Assistant!** 🏠💨