# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/blakinio/thesslagreen.svg)](https://github.com/blakinio/thesslagreen/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.1.0%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org/)

Lokalna integracja (hub) dla rekuperatorów ThesslaGreen AirPack przez Modbus.
Repozytorium zawiera integrację Home Assistant z konfiguracją przez UI, automatycznym skanowaniem rejestrów oraz zestawem serwisów do sterowania urządzeniem.

## Wymagania

- Home Assistant **2026.1.0+**
- Python **3.12+**
- `pymodbus>=3.6.0` (instalowane przez integrację)

## Co obsługuje integracja

- **Transporty:** Modbus TCP oraz Modbus RTU/USB.
- **Urządzenia:** ThesslaGreen AirPack Home (serie zgodne z protokołem Modbus producenta).
- **Konfiguracja przez UI:** `config_flow` + opcje integracji.
- **Auto-detekcja możliwości urządzenia:** tworzone są tylko encje dla dostępnych rejestrów/funkcji.
- **Diagnostyka:** dane diagnostyczne urządzenia i serwis do podniesienia poziomu logowania.
- **Tryb pełnej listy rejestrów (opcjonalny):** do diagnostyki i porównań po aktualizacji firmware.

> Integracja korzysta z definicji rejestrów z pliku JSON i mapowania encji. Nie każdy wykryty rejestr musi mieć osobną encję w Home Assistant.

## Instalacja

### HACS (zalecane)

1. HACS → **Integrations** → menu `⋮` → **Custom repositories**.
2. Dodaj URL: `https://github.com/blakinio/thesslagreen`.
3. Kategoria: **Integration**.
4. Zainstaluj „ThesslaGreen Modbus” i zrestartuj Home Assistant.

### Ręcznie

```bash
cd /config
git clone https://github.com/blakinio/thesslagreen.git
cp -r thesslagreen/custom_components/thessla_green_modbus custom_components/
```

## Serwisy

Integracja udostępnia serwisy m.in. do:

- trybów specjalnych,
- harmonogramu przepływu,
- parametrów bypass/GWC,
- progów jakości powietrza,
- resetów,
- odświeżenia danych,
- pełnego skanu rejestrów,
- czasowego podniesienia poziomu logów.

Pełna lista: [`custom_components/thessla_green_modbus/services.yaml`](custom_components/thessla_green_modbus/services.yaml).

## Diagnostyka i problemy

- Włącz debug logi integracji:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
```

- Sprawdź szczegóły błędów i statystyk przez „Pobierz diagnostykę” w Home Assistant.
- Upewnij się, że tylko jedno narzędzie utrzymuje aktywne połączenie Modbus do urządzenia.

## Dokumentacja dodatkowa

- [Diagnostyka](docs/diagnostics.md)
- [Skanowanie rejestrów](docs/register_scanning.md)
- [Migracja encji przepływu](docs/airflow_migration.md)
- [Changelog](CHANGELOG.md)

## Rozwój i testy

Uruchamianie testów:

```bash
pytest
```

Kontrybucja: [CONTRIBUTING.md](CONTRIBUTING.md).
