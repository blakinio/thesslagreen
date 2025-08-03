# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/YOUR_USERNAME/thessla_green_modbus.svg)](https://github.com/YOUR_USERNAME/thessla_green_modbus/releases)

Inteligentna integracja dla Home Assistant umożliwiająca kontrolę rekuperatorów ThesslaGreen AirPack przez protokół Modbus RTU/TCP.

## ✨ Kluczowe funkcje

- **🔍 Inteligentne skanowanie urządzenia** - automatycznie wykrywa dostępne funkcje
- **📱 Tylko aktywne entycje** - tworzy tylko te entycje, które są rzeczywiście dostępne
- **🏠 Pełna kontrola rekuperatora** - tryby pracy, intensywność, temperatury
- **📊 Kompletny monitoring** - wszystkie czujniki, statusy, alarmy
- **🌡️ Entycja Climate** - łatwa kontrola z interfejsu HA
- **⚡ Funkcje specjalne** - okap, kominek, wietrzenie, pusty dom
- **🌿 Systemy GWC i Bypass** - pełna kontrola systemów dodatkowych

## 🚀 Instalacja

### HACS (Rekomendowane)

1. Dodaj to repozytorium jako custom repository w HACS:
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/YOUR_USERNAME/thessla_green_modbus`
   - Category: Integration

2. Znajdź "ThesslaGreen Modbus" w HACS i zainstaluj

3. Zrestartuj Home Assistant

### Manualna instalacja

1. Pobierz najnowszą wersję z [Releases](https://github.com/YOUR_USERNAME/thessla_green_modbus/releases)
2. Wypakuj do `custom_components/thessla_green_modbus/`
3. Zrestartuj Home Assistant

## ⚙️ Konfiguracja

1. Przejdź do **Ustawienia** → **Integracje**
2. Kliknij **+ DODAJ INTEGRACJĘ**
3. Wyszukaj **ThesslaGreen Modbus**
4. Podaj dane połączenia:
   - **Host**: IP rekuperatora
   - **Port**: 502 (domyślny Modbus TCP)
   - **Slave ID**: 10 (domyślny)
5. Kliknij **DODAJ**

Integracja automatycznie przeskanuje urządzenie i utworzy tylko dostępne entycje.

## 📋 Obsługiwane urządzenia

- AirPack Home (wszystkie warianty: h/v/f, Energy/Energy+)
- AirPack Home 200f-850h
- Wszystkie modele z protokołem Modbus RTU/TCP

## 🌡️ Entycje

### Sensory temperatury
- Temperatura zewnętrzna (TZ1)
- Temperatura nawiewu (TN1)
- Temperatura wywiewu (TP)
- Temperatura FPX (TZ2)
- Temperatura kanałowa (TN2)
- Temperatura GWC (TZ3)
- Temperatura otoczenia (TO)

### Sensory przepływu
- Strumień nawiewu (m³/h)
- Strumień wywiewu (m³/h)
- Intensywność nawiewu (%)
- Intensywność wywiewu (%)

### Kontrola
- **Tryby pracy**: Automatyczny, Manualny, Chwilowy
- **Intensywność wentylacji**: 10-150%
- **Temperatura nawiewu**: 20-45°C (tryb KOMFORT)
- **Funkcje specjalne**: OKAP, KOMINEK, WIETRZENIE, PUSTY DOM

### Systemy dodatkowe
- **GWC (Gruntowy Wymiennik Ciepła)**
  - Tryb: Zima/Lato/Nieaktywny
  - Regeneracja: Dobowa/Temperaturowa
  - Progi temperatur
- **Bypass**
  - Tryb: FreeHeating/FreeCooling/Nieaktywny
  - Różne sposoby pracy
- **Constant Flow**
  - Status aktywności
  - Rzeczywiste przepływy

### Alarmy i diagnostyka
- **Alarmy typu S** (błędy zatrzymujące)
- **Alarmy typu E** (ostrzeżenia)
- Statusy czujników
- Zabezpieczenia termiczne
- Kontrola filtrów

## 🔧 Zaawansowana konfiguracja

### Opcje konfiguracyjne
- **Częstotliwość odczytu**: 10-300 sekund
- **Timeout**: 5-60 sekund
- **Retry**: 1-5 prób
- **Skanowanie urządzenia**: włącz/wyłącz

### Automatyzacje

```yaml
# Przykład: Włącz funkcję OKAP gdy gotujemy
automation:
  - alias: "Okap podczas gotowania"
    trigger:
      - platform: state
        entity_id: input_boolean.gotowanie
        to: 'on'
    action:
      - service: select.select_option
        target:
          entity_id: select.thessla_special_mode
        data:
          option: "OKAP"
```

## 🐛 Rozwiązywanie problemów

### Połączenie
- Sprawdź IP i port urządzenia
- Upewnij się, że Modbus TCP jest włączony
- Sprawdź konfigurację sieci

### Brak entycji
- Uruchom **Ponowne skanowanie** w opcjach integracji
- Sprawdź logi HA: `custom_components.thessla_green_modbus`
- Niektóre funkcje mogą nie być dostępne w Twoim modelu

### Wydajność
- Zwiększ **Częstotliwość odczytu** jeśli HA jest wolny
- Zmniejsz **Retry** dla szybszego timeout

## 📝 Logi

Domyślnie integracja zapisuje tylko podstawowe ostrzeżenia. Aby włączyć rozszerzone logowanie diagnostyczne, w tym szczegółowe informacje o statusie urządzenia, dodaj w `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.thessla_green_modbus: debug
    pymodbus: debug
```

## 🤝 Wsparcie

- [Issues](https://github.com/YOUR_USERNAME/thessla_green_modbus/issues)
- [Discussions](https://github.com/YOUR_USERNAME/thessla_green_modbus/discussions)
- [Wiki](https://github.com/YOUR_USERNAME/thessla_green_modbus/wiki)

## 📄 Licencja

MIT License - zobacz [LICENSE](LICENSE)

## 🙏 Podziękowania

- [ThesslaGreen](https://thesslagreen.com) za dokumentację Modbus
- Home Assistant Community
- Wszyscy testerzy i kontrybutorzy