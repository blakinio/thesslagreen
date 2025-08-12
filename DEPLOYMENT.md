# ThesslaGreen Modbus Integration - Przewodnik Wdrożenia

## 📋 Wymagania

### Sprzęt
- Rekuperator ThesslaGreen AirPack z modułem Modbus TCP
- Home Assistant z dostępem do sieci lokalnej
- Połączenie sieciowe między HA a rekuperatorem

### Oprogramowanie
- Home Assistant 2025.7.1 lub nowszy (minimalna wersja zadeklarowana w `manifest.json`, brak pakietu `homeassistant` w `requirements.txt`)
- Python 3.12 lub nowszy
- Biblioteka `pymodbus>=3.0.0`

## 🚀 Instalacja

### Opcja 1: HACS (Rekomendowane)

1. **Dodaj repozytorium custom w HACS:**
   - Otwórz HACS → Integrations
   - Kliknij ⋮ → Custom repositories
   - URL: `https://github.com/thesslagreen/thessla-green-modbus-ha`
   - Category: Integration
   - Kliknij ADD

2. **Zainstaluj integrację:**
   - Znajdź "ThesslaGreen Modbus" w HACS
   - Kliknij INSTALL
   - Zrestartuj Home Assistant

### Opcja 2: Instalacja manualna

1. **Pobierz pliki:**
   ```bash
   cd /config
   git clone https://github.com/thesslagreen/thessla-green-modbus-ha.git
   ```

2. **Skopiuj do custom_components:**
   ```bash
   cp -r thessla_green_modbus/custom_components/thessla_green_modbus custom_components/
   ```

3. **Zrestartuj Home Assistant**

## ⚙️ Konfiguracja Urządzenia

### Konfiguracja Rekuperatora

1. **Włącz Modbus TCP w rekuperatorze:**
   - Menu → Komunikacja → Modbus TCP
   - Włącz: TAK
   - Port: 502 (domyślny)
   - ID urządzenia: 10 (domyślny)

2. **Skonfiguruj sieć:**
   - Ustaw statyczny IP dla rekuperatora
   - Upewnij się, że HA ma dostęp do tej sieci

### Dodanie Integracji w HA

1. **Przejdź do Ustawienia → Integracje**
2. **Kliknij + DODAJ INTEGRACJĘ**
3. **Wyszukaj "ThesslaGreen Modbus"**
4. **Wprowadź dane:**
   - **Host**: IP rekuperatora (np. 192.168.1.100)
   - **Port**: 502
   - **ID urządzenia**: 10
   - **Nazwa**: ThesslaGreen AirPack

5. **Kliknij DODAJ**

## 🔧 Konfiguracja Zaawansowana

### Opcje Integracji

Aby zmienić ustawienia:
1. Idź do Ustawienia → Integracje
2. Znajdź ThesslaGreen Modbus
3. Kliknij KONFIGURUJ

**Dostępne opcje:**
- **Częstotliwość odczytu**: 10-300 sekund (domyślnie 30s)
- **Timeout**: 5-60 sekund (domyślnie 10s)
- **Retry**: 1-5 prób (domyślnie 3)

### Optymalizacja Wydajności

**Dla sieci Wi-Fi:**
```yaml
# Zwiększ interwały dla stabilności
scan_interval: 60
timeout: 15
retry: 2
```

**Dla sieci Ethernet:**
```yaml
# Szybsze odczyty dla lepszej responsywności
scan_interval: 15
timeout: 5
retry: 3
```

## 📊 Dostępne Entycje

### Automatycznie Wykrywane

Integracja automatycznie wykrywa dostępne funkcje i tworzy tylko istniejące entycje:

**Sensory:**
- Temperatury (zewnętrzna, nawiew, wywiew, FPX, GWC)
- Przepływy powietrza (m³/h)
- Intensywność wentylacji (%)
- Wersja firmware i numer seryjny

**Kontrolki:**
- Tryb pracy (Auto/Manual/Temporary)
- Intensywność wentylacji
- Temperatury komfortu
- Funkcje specjalne (OKAP, KOMINEK, etc.)

**Systemy:**
- GWC (Gruntowy Wymiennik Ciepła)
- Bypass
- Constant Flow
- Nagrzewnice/Chłodnice

### Entycja Climate

Główna entycja do kontroli rekuperatora:
- Tryby HVAC: Auto, Fan Only, Off
- Kontrola temperatury (jeśli dostępna)
- Tryby wentylatora (10%-150%, Boost)
- Dodatkowe informacje w atrybutach

## 🏠 Przykłady Automatyzacji

### Włączenie OKAP podczas gotowania

```yaml
automation:
  - alias: "Okap podczas gotowania"
    trigger:
      - platform: state
        entity_id: input_boolean.gotowanie
        to: 'on'
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_special_function
        data:
          option: "OKAP"
      - delay: '00:30:00'  # 30 minut
      - service: select.select_option
        target:
          entity_id: select.thessla_special_function
        data:
          option: "Wyłączone"
```

### Automatyczna kontrola sezonowa

```yaml
automation:
  - alias: "Tryb zimowy"
    trigger:
      - platform: numeric_state
        entity_id: sensor.thessla_outside_temperature
        below: 10
        for: '01:00:00'
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_season_mode
        data:
          option: "Zima"

  - alias: "Tryb letni"
    trigger:
      - platform: numeric_state
        entity_id: sensor.thessla_outside_temperature
        above: 20
        for: '01:00:00'
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_season_mode
        data:
          option: "Lato"
```

### Kontrola jakości powietrza

```yaml
automation:
  - alias: "Zwiększ wentylację przy złej jakości powietrza"
    trigger:
      - platform: state
        entity_id: binary_sensor.thessla_contamination_sensor
        to: 'on'
    action:
      - service: number.set_value
        target:
          entity_id: number.thessla_air_flow_rate_manual
        data:
          value: 80
      - service: select.select_option
        target:
          entity_id: select.thessla_mode
        data:
          option: "Manualny"
```

## 🐛 Rozwiązywanie Problemów

### Nie można połączyć się z urządzeniem

1. **Sprawdź sieć:**
   ```bash
   ping [IP_REKUPERATORA]
   telnet [IP_REKUPERATORA] 502
   ```

2. **Sprawdź konfigurację Modbus:**
   - Czy Modbus TCP jest włączony?
   - Czy port 502 jest otwarty?
   - Czy ID urządzenia jest poprawne?

3. **Sprawdź firewall:**
   - Czy HA ma dostęp do portu 502?
   - Czy rekuperator blokuje połączenia?

### Brak niektórych entycji

1. **Uruchom ponowne skanowanie:**
   - Integracje → ThesslaGreen → Konfiguruj
   - Lub usuń i dodaj ponownie integrację

2. **Sprawdź model rekuperatora:**
   - Nie wszystkie funkcje są dostępne w każdym modelu
   - Sprawdź dokumentację Modbus dla Twojego modelu

3. **Sprawdź logi:**
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.thessla_green_modbus: debug
   ```

### Powolne odczyty/timeouty

1. **Zwiększ timeout:**
   - Integracje → ThesslaGreen → Konfiguruj
   - Timeout: 15-30 sekund

2. **Zmniejsz częstotliwość:**
   - Scan interval: 60-120 sekund

3. **Sprawdź sieć:**
   - Użyj połączenia Ethernet zamiast Wi-Fi
   - Sprawdź jakość sygnału Wi-Fi

### Błędy w logach

**"ModbusIOException":**
- Problem z połączeniem sieciowym
- Sprawdź dostępność urządzenia

**"ModbusException":**
- Nieprawidłowy adres rejestru
- Funkcja niedostępna w Twoim modelu

**"Invalid register value":**
- Czujnik odłączony lub uszkodzony
- Wartość spoza zakresu

## 📈 Monitoring i Diagnostyka

### Włączenie szczegółowych logów

```yaml
logger:
  default: warning
  logs:
    custom_components.thessla_green_modbus: debug
    pymodbus: info
```

### Dashboard przykładowy

```yaml
type: entities
entities:
  - entity: climate.thessla_green_klimat
  - entity: sensor.thessla_outside_temperature
  - entity: sensor.thessla_supply_temperature
  - entity: sensor.thessla_supply_flow_rate
  - entity: select.thessla_mode
  - entity: select.thessla_special_function
  - entity: binary_sensor.thessla_constant_flow_active
title: ThesslaGreen AirPack
```

### Karty graficzne

```yaml
type: history-graph
entities:
  - sensor.thessla_outside_temperature
  - sensor.thessla_supply_temperature
  - sensor.thessla_exhaust_temperature
hours_to_show: 24
refresh_interval: 60
title: Temperatury
```

## 🔄 Aktualizacje

### HACS
1. HACS → Integrations
2. Znajdź ThesslaGreen Modbus
3. Kliknij UPDATE (jeśli dostępne)
4. Zrestartuj HA

### Manualna
1. Pobierz nową wersję z GitHub
2. Zastąp pliki w `custom_components/thessla_green_modbus/`
3. Zrestartuj HA

## 📞 Wsparcie

- **GitHub Issues**: https://github.com/thesslagreen/thessla-green-modbus-ha/issues
- **Community Forum**: https://github.com/thesslagreen/thessla-green-modbus-ha/discussions
- **Wiki**: https://github.com/thesslagreen/thessla-green-modbus-ha/wiki

## ⚠️ Uwagi Bezpieczeństwa

1. **Nie eksponuj Modbus TCP na internet**
2. **Używaj VPN dla dostępu zdalnego**
3. **Regularnie aktualizuj integrację**
4. **Monitoruj logi pod kątem podejrzanej aktywności**

## 📄 Licencja

MIT License - zobacz plik LICENSE w repozytorium.