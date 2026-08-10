# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.1.0%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://python.org/)

Lokalna integracja (hub) dla rekuperatorów ThesslaGreen AirPack przez Modbus.
Repozytorium zawiera integrację Home Assistant z konfiguracją przez UI, automatyczną detekcją dostępnych funkcji urządzenia, walidacją znanych rejestrów oraz zestawem akcji do sterowania urządzeniem.

## Wymagania

- Home Assistant **2026.1.0+**
- Python **3.13+**
- `pymodbus>=3.6.0,<4.0` (instalowane przez integrację)

## Co obsługuje integracja

- **Transporty:** Modbus TCP, RTU-over-TCP oraz Modbus RTU/USB.
- **Urządzenia:** ThesslaGreen AirPack Home zgodne z obsługiwanym protokołem Modbus producenta.
- **Konfiguracja przez UI:** `config_flow` + opcje integracji.
- **Auto-detekcja możliwości urządzenia:** tworzone są tylko encje dla dostępnych rejestrów/funkcji.
- **Diagnostyka:** dane diagnostyczne urządzenia i akcja do czasowego podniesienia poziomu logowania.
- **Walidacja znanych rejestrów:** `validate_known_registers` korzysta z kontrolowanej ścieżki I/O koordynatora.
- **Skan diagnostyczny (advanced):** `scan_all_registers` jest izolowany od normalnego pollingu; na czas skanu główny transport jest rozłączany, skan używa skonfigurowanego typu transportu, a po zakończeniu połączenie jest odtwarzane.
- **Błędy zapisu:** końcowe niepowodzenie Modbus jest zgłaszane do Home Assistanta; follow-up hardening dodaje także wpis Repairs, który znika po następnym potwierdzonym zapisie.
- **Szacowanie mocy:** `electrical_power` jest estymacją chwilową, nie licznikiem energii. Integracja nie publikuje procesu-pamięciowego `total_energy` jako trwałego pomiaru energii.

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

## Modbus RTU / USB

Dla instalacji produkcyjnej preferuj trwałą ścieżkę urządzenia, np.:

```text
/dev/serial/by-id/usb-...
```

Zamiast `/dev/ttyUSB0`, ponieważ numer `ttyUSB` może zmienić się po restarcie hosta lub ponownym podłączeniu adaptera. Ustaw baud rate, parity, stop bits i slave ID zgodnie z konfiguracją centrali.

## Akcje / serwisy

Integracja udostępnia akcje m.in. do:

- trybów specjalnych,
- harmonogramu przepływu,
- parametrów bypass/GWC,
- progów jakości powietrza,
- resetów,
- odświeżenia danych,
- bezpiecznej walidacji znanych rejestrów (`validate_known_registers`),
- pełnego diagnostycznego skanu rejestrów (`scan_all_registers`),
- czasowego podniesienia poziomu logów.

Pełna lista: [`custom_components/thessla_green_modbus/services.yaml`](custom_components/thessla_green_modbus/services.yaml).

## Diagnostyka i problemy

Włącz debug logi integracji:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
```

- Sprawdź szczegóły błędów i statystyk przez „Pobierz diagnostykę” w Home Assistant.
- Upewnij się, że zewnętrzne narzędzia nie utrzymują konkurencyjnego połączenia Modbus do tej samej centrali podczas normalnej pracy integracji.
- Do normalnej klasyfikacji znanych rejestrów preferuj `validate_known_registers`.

> **⚠ `scan_all_registers` — advanced diagnostics:**
> pełny skan jest operacją ciężką i może potrwać długo. Integracja izoluje go od normalnego I/O i odtwarza główny transport po zakończeniu, ale nie należy używać go jako cyklicznej automatyzacji.

> **Status jakości:** manifest deklaruje `quality_scale: bronze`. Aktualny stan automatycznych i sprzętowych dowodów jest opisany w [`docs/quality/STATUS.md`](docs/quality/STATUS.md) oraz [`docs/real_device_validation.md`](docs/real_device_validation.md).

## Dokumentacja dodatkowa

- [Kanoniczny status jakości](docs/quality/STATUS.md)
- [Audyt HA Quality Scale](docs/ha_quality_scale_audit.md)
- [Walidacja na urządzeniu fizycznym](docs/real_device_validation.md)
- [Gotowość wydania](docs/release_readiness.md)
- [Proces wydawania](docs/release_process.md)
- [Architektura docelowa](docs/thesslagreen_architecture.md)
- [Inwentarz plików (architektura)](docs/architecture/file_inventory.md)
- [Przepływ runtime (architektura)](docs/architecture/runtime_flow.md)
- [Ścieżka zapisu i read-back (architektura)](docs/architecture/write_path.md)
- [Wytyczne refaktoryzacji](docs/thesslagreen_guidelines.md)
- [Status refaktoryzacji](docs/refactor_status.md)
- [Changelog](CHANGELOG.md)

## Rozwój i testy

**Python 3.13 jest wymagany** (zgodnie z Home Assistant 2026.1+ i `pyproject.toml`).

```bash
pip install -r requirements-dev.txt
ruff check custom_components tests tools
ruff check --select I custom_components tests tools
ruff format --check custom_components tests tools
mypy custom_components/thessla_green_modbus
pytest tests/ -q
python tools/validate_entity_mappings.py
python tools/check_translations.py
```

CI dodatkowo uruchamia Hassfest, HACS validation, porównanie rejestrów z referencją producenta oraz skupiony test kontraktów API na minimalnej deklarowanej wersji Home Assistant `2026.1.0`.

Lekki smoke-check bez pełnego środowiska Home Assistant:

```bash
pip install -r requirements-test-min.txt
python tools/validate_registers.py
```

To sprawdzenie jest również uruchamiane przez `pre-commit` (hook `validate-registers`).

> **Refactor constraints (must keep):** no legacy modules, no compatibility/re-export/proxy shims; `core/`, `transport/`, `registers/`, and `scanner/` must not import Home Assistant; coordinator package migration is completed (`coordinator/` is canonical, top-level `coordinator.py` removed). Further broad read-path consolidation is deliberately deferred until longer real-device validation; see [`docs/core_consolidation_plan.md`](docs/core_consolidation_plan.md).
