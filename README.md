# ThesslaGreen Modbus Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/thesslagreen/thessla-green-modbus-ha.svg)](https://github.com/thesslagreen/thessla-green-modbus-ha/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.7.1%2B-blue.svg)](https://home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org/)

## ✨ Kompletna integracja ThesslaGreen AirPack z Home Assistant

Najkompletniejsza integracja dla rekuperatorów ThesslaGreen AirPack z protokołem Modbus TCP/RTU. Obsługuje **wszystkie 200+ rejestrów** z dokumentacji MODBUS_USER_AirPack_Home_08.2021.01 bez wyjątku.
Integracja działa jako **hub** w Home Assistant.

### 🚀 Kluczowe funkcje v2.1+

- **🔍 Inteligentne skanowanie urządzenia** - automatycznie wykrywa dostępne funkcje i rejestry
- **📱 Tylko aktywne encje** - tworzy tylko te encje, które są rzeczywiście dostępne
- **🏠 Kompletna kontrola rekuperatora** - wszystkie tryby pracy, temperatury, przepływy
- **📊 Pełny monitoring** - wszystkie czujniki, statusy, alarmy, diagnostyka
- **🔋 Szacowanie zużycia energii** - wbudowane czujniki mocy i energii
- **💨 Obsługa Constant Flow** - wykrywanie rejestrów `supply_air_flow`, `exhaust_air_flow` oraz procedury HEWR
- **🌡️ Zaawansowana encja Climate** - pełna kontrola z preset modes i trybami specjalnymi
- **⚡ Wszystkie funkcje specjalne** - OKAP, KOMINEK, WIETRZENIE, PUSTY DOM, BOOST
- **🌿 Systemy GWC i Bypass** - kompletna kontrola systemów dodatkowych
- **📅 Harmonogram tygodniowy** - pełna konfiguracja programów czasowych
- **🛠️ 14 serwisów** - kompletne API do automatyzacji i kontroli, w tym pełny skan rejestrów
- **🔧 Diagnostyka i logowanie** - szczegółowe informacje o błędach i wydajności
- **🌍 Wsparcie wielojęzyczne** - polski i angielski

## 📋 Kompatybilność

### Urządzenia
- ✅ **ThesslaGreen AirPack Home Series 4** - wszystkie modele
- ✅ **AirPack Home 300v-850h** (Energy+, Energy, Enthalpy)
- ✅ **Protokół Modbus TCP/RTU** z auto-detekcją
- ✅ **Firmware v3.x - v5.x** z automatyczną detekcją

### Home Assistant
- ✅ **Wymagany Home Assistant 2025.7.1+** — minimalna wersja określona w `manifest.json` (pakiet `homeassistant` nie jest częścią `requirements.txt`)
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
- ID urządzenia: **10** (domyślny)

### 2. Dodaj integrację w Home Assistant
1. **Ustawienia** → **Integracje** → **+ DODAJ INTEGRACJĘ**
2. Wyszukaj **"ThesslaGreen Modbus"**
3. Wprowadź dane:
   - **IP Address**: IP rekuperatora (np. 192.168.1.100)
   - **Port**: 502
   - **ID urządzenia**: 10
4. Integracja automatycznie przeskanuje urządzenie
5. Kliknij **DODAJ**

### 3. Opcje zaawansowane
- **Interwał skanowania**: 10-300s (domyślnie 30s)
- **Timeout**: 5-60s (domyślnie 10s)
- **Retry**: 1-5 prób (domyślnie 3)
- **Backoff**: 0-5s opóźnienia między próbami (domyślnie 0, wykładniczy)
- **Pełna lista rejestrów**: Pomiń skanowanie (może powodować błędy)
- **Ustawienia UART**: Skanuj opcjonalne rejestry konfiguracji portu (0x1168-0x116B)
- **Airflow unit**: wybierz `m³/h` (domyślnie) lub `percentage`

#### Pełna lista rejestrów

Włączenie tej opcji pomija proces autoskanu i tworzy komplet około 300 encji,
niezależnie od tego, czy dane rejestry są obsługiwane przez urządzenie. Można
ją aktywować z poziomu interfejsu Home Assistant: **Ustawienia → Integracje →
ThesslaGreen Modbus → Konfiguruj → Pełna lista rejestrów**. Należy stosować ją
ostrożnie, ponieważ urządzenie może zgłaszać błędy dla nieobsługiwanych
rejestrów.

Adresy rejestrów, które wielokrotnie nie odpowiadają, są automatycznie
pomijane w kolejnych skanach.

Szczegóły migracji z czujników procentowych opisano w pliku [docs/airflow_migration.md](docs/airflow_migration.md).

### Proces autoskanu
Podczas dodawania integracji moduł `ThesslaGreenDeviceScanner` (plik
`scanner_core.py`) wywołuje metodę `ThesslaGreenDeviceScanner.scan_device()`,
która otwiera połączenie Modbus, wykrywa dostępne rejestry oraz
możliwości urządzenia, a następnie zamyka klienta. Wynik skanowania
trafia do struktury `available_registers`, z której koordynator tworzy
jedynie encje obsługiwane przez dane urządzenie. Jeśli po aktualizacji
firmware pojawią się nowe rejestry, ponownie uruchom skanowanie (np.
usuń i dodaj integrację), aby zaktualizować listę `available_registers`.

Podczas skanowania rejestry są grupowane według funkcji i tylko część z nich
przekłada się na utworzone encje. Niektóre służą jedynie do diagnostyki lub
ustawień i nie mają bezpośredniego odzwierciedlenia w Home Assistant.
Integracja może wykryć 200+ rejestrów, ale utworzyć ~100 encji.
> 🔎 Wiele wykrytych rejestrów to bloki konfiguracji lub wartości
> wielorejestrowe, które nie mają bezpośredniego odwzorowania na encje
> Home Assistant. Domyślnie integracja udostępnia tylko rejestry
> zdefiniowane w [`entity_mappings.py`](custom_components/thessla_green_modbus/entity_mappings.py).
> Włączenie opcji **Pełna lista rejestrów** (`force_full_register_list`)
> tworzy encje dla każdego znalezionego rejestru, lecz może ujawnić
> niekompletne dane lub pola konfiguracyjne – używaj jej ostrożnie.
> [Więcej informacji](docs/register_scanning.md).

### Pełny skan rejestrów
Dostępny jest serwis `thessla_green_modbus.scan_all_registers`, który wykonuje
pełne skanowanie wszystkich rejestrów (`full_register_scan=True`) i zwraca
listę nieznanych adresów. Operacja może trwać kilka minut i znacząco obciąża
urządzenie – używaj jej tylko do diagnostyki.
### Użycie `group_reads`
Funkcja `group_reads` dzieli listę adresów na ciągłe bloki ograniczone parametrem `max_block_size` (domyślnie 64). Własne skrypty powinny z niej korzystać, aby minimalizować liczbę zapytań i nie przekraczać zalecanego rozmiaru bloku. W razie problemów z komunikacją można zmniejszyć `max_block_size`, np. do 16, co zapewnia stabilniejszy odczyt.

```python
from custom_components.thessla_green_modbus.loader import group_reads

for start, size in group_reads(range(100), max_block_size=16):
    print(start, size)
```


### Rejestry w formacie JSON
Definicje rejestrów znajdują się wyłącznie w pliku
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`,
który stanowi kanoniczne źródło prawdy (dawny katalog `registers/` został usunięty).
Każdy wpis w sekcji `registers` zawiera m.in. pola:

- `function` – kod funkcji Modbus (`01`–`04`)
- `address_dec` / `address_hex` – adres rejestru
- `name` – unikalna nazwa w formacie snake_case
- `description` – opis z dokumentacji
- `access` – tryb dostępu (`R`/`W`)

Opcjonalnie można określić `unit`, `enum`, `multiplier`, `resolution` oraz inne
metadane. Aby dodać nowy rejestr, dopisz obiekt do listy `registers` zachowując
porządek adresów i uruchom `pytest tests/test_register_loader.py`, aby
zweryfikować poprawność pliku.

### Włączanie logów debug
W razie problemów możesz włączyć szczegółowe logi tej integracji. Dodaj poniższą konfigurację do `configuration.yaml` i zrestartuj Home Assistant:

```yaml
logger:
  logs:
    custom_components.thessla_green_modbus: debug
```

Poziom `debug` pokaże m.in. surowe i przetworzone wartości rejestrów oraz ostrzeżenia o niedostępnych czujnikach lub wartościach poza zakresem.

## 📊 Dostępne encje

### Sensory (50+ automatycznie wykrywanych)
- **Temperatury**: Zewnętrzna, nawiew, wywiew, FPX, GWC, kanałowa, otoczenia
- **Przepływy**: Nawiew, wywiew, rzeczywisty, min/max zakresy
- **Ciśnienia**: Nawiew, wywiew, różnicowe, alarmy
- **Jakość powietrza**: CO2, VOC, indeks jakości, wilgotność
- **Energie**: Zużycie, odzysk, moc szczytowa, średnia, roczna redukcja CO2 (kg)
- **System**: Obliczona sprawność, godziny pracy, status filtrów, błędy
- **Diagnostyka**: Czas aktualizacji, jakość danych, statystyki

### Sensory binarne (40+ automatycznie wykrywanych)
- **Status systemu**: Zasilanie wentylatorów, bypass, GWC, pompy
- **Tryby**: Letni/zimowy, auto/manual, tryby specjalne (boost, eco, away, sleep, fireplace, hood, party, bathroom, kitchen, summer, winter)
- **Wejścia**: Expansion, alarm pożarowy, czujnik zanieczyszczenia
- **Błędy i alarmy**: Wszystkie kody S1-S32 i E99-E105
- **Zabezpieczenia**: Termiczne, przeciwmrozowe, przeciążenia

### Kontrolki (30+ automatycznie wykrywanych)
- **Climate**: Kompletna kontrola HVAC z preset modes
- **Switches**: Wszystkie systemy, tryby, konfiguracja
- **Numbers**: Temperatury, intensywności, czasy, limity alarmów
- **Selects**: Tryby pracy, tryb sezonowy, harmonogram, komunikacja, język

## 🛠️ Serwisy (14 kompletnych serwisów)

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
Czujnik `sensor.thessla_error_codes` agreguje zarówno kody błędów (`E*`), jak i kody statusowe (`S*`).
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
            Kod błędu: {{ states('sensor.thessla_error_codes') }}
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
3. Spróbuj różnych ID urządzenia (integracja auto-wykrywa 1, 10, 247)
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


### Kody wyjątków Modbus i brakujące rejestry
Podczas skanowania urządzenia mogą pojawić się odpowiedzi z kodami wyjątków Modbus,
gdy dany rejestr nie jest obsługiwany. Najczęściej spotykane kody to:

- `2` – Illegal Data Address (rejestr nie istnieje)
- `3` – Illegal Data Value (wartość poza zakresem)
- `4` – Slave Device Failure (błąd urządzenia)

W takich przypadkach integracja zapisuje w logach komunikaty w stylu:

```
Skipping unsupported input registers 120-130
```

Są to wpisy informacyjne i zazwyczaj oznaczają, że urządzenie po prostu nie posiada
tych rejestrów. Można je bezpiecznie zignorować.
=======
### Komunikaty „Skipping unsupported … registers”
Podczas skanowania integracja próbuje odczytać grupy rejestrów.  
Jeśli rekuperator nie obsługuje danego zakresu, w logach pojawia się ostrzeżenie w stylu:

```
Skipping unsupported input registers 0x0100-0x0102 (exception code 2)
```

Kody wyjątków Modbus informują, dlaczego odczyt się nie powiódł:

- **2 – Illegal Data Address** – rejestry nie istnieją w tym modelu
- **3 – Illegal Data Value** – rejestry istnieją, ale urządzenie odrzuciło żądanie (np. funkcja wyłączona)
- **4 – Slave Device Failure** – urządzenie nie potrafiło obsłużyć żądania

Jednorazowe ostrzeżenia pojawiające się przy początkowym skanowaniu lub
dotyczące opcjonalnych funkcji można zwykle zignorować.  
Jeśli jednak powtarzają się dla kluczowych rejestrów, sprawdź konfigurację,
podłączenie i wersję firmware.


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
- ✅ **Monitoring**: Wydajność energetyczna (`sensor.calculated_efficiency`) i czas pracy

### Wydajność
- **Optymalizowane odczyty**: Grupowanie rejestrów, 60% mniej wywołań Modbus
- **Auto-skanowanie**: Tylko dostępne rejestry, brak błędów
- **Diagnostyka**: Szczegółowe metryki wydajności i błędów
- **Stabilność**: Retry logic, fallback reads, graceful degradation

## 🧹 Czyszczenie starych encji

Po aktualizacji integracji możesz usunąć nieużywane encje przy pomocy
skryptu `tools/cleanup_old_entities.py`.

```bash
python3 tools/cleanup_old_entities.py
```

Skrypt domyślnie obsługuje polskie i angielskie nazwy **starych** encji
(`number.rekuperator_predkosc`, `number.rekuperator_speed`).
Aktualna encja wentylatora to `fan.rekuperator_fan` – upewnij się, że Twoje
automatyzacje odwołują się do niej zamiast do usuniętej `number.rekuperator_predkosc`.

### Dodatkowe wzorce

Możesz dodać własne wzorce poprzez opcję CLI lub plik konfiguracyjny:

```bash
python3 tools/cleanup_old_entities.py \
    --pattern "thessla.*ventilation_speed" \
    --pattern "number.extra_sensor"
```

Plik JSON z dodatkowymi wzorcami (domyślnie `cleanup_config.json` obok skryptu):

```json
{
  "old_entity_patterns": ["thessla.*ventilation_speed"]
}
```

Uruchomienie z własnym plikiem:

```bash
python3 tools/cleanup_old_entities.py \
    --config my_cleanup_config.json
```

## 🤝 Wsparcie i rozwój

### Dokumentacja
- 📖 [Pełna dokumentacja](https://github.com/thesslagreen/thessla-green-modbus-ha/wiki)
- 🔧 [Konfiguracja zaawansowana](DEPLOYMENT.md)
- 🚀 [Quick Start Guide](QUICK_START.md)

### Wsparcie
- 🐛 [Zgłaszanie błędów](https://github.com/thesslagreen/thessla-green-modbus-ha/issues)
- 💡 [Propozycje funkcji](https://github.com/thesslagreen/thessla-green-modbus-ha/discussions)
- 🤝 [Contributing](CONTRIBUTING.md)

### Generowanie `registers.py` (opcjonalne)
Integracja korzysta bezpośrednio z pliku
`custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`,
który stanowi jedyne źródło prawdy o rejestrach. Skrypt
`tools/generate_registers.py` może wygenerować pomocniczy moduł
`registers.py` dla zewnętrznych narzędzi, lecz plik ten nie jest
przechowywany w repozytorium.

```bash
python tools/generate_registers.py  # jeśli potrzebujesz statycznej mapy
```

### Validate translations
Ensure translation files are valid JSON:

```bash
python -m json.tool custom_components/thessla_green_modbus/translations/*.json
```

### Changelog
Zobacz [CHANGELOG.md](CHANGELOG.md) dla pełnej historii zmian.

## Rejestry w formacie JSON

Plik `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` przechowuje komplet
definicji rejestrów i stanowi jedyne źródło prawdy. Wszystkie narzędzia w
`tools/` operują wyłącznie na tym formacie.

### Format pliku

Każdy wpis w pliku to obiekt z polami:

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

Opcjonalnie można dodać `enum`, `multiplier`, `resolution`, `min`, `max`.

### Dodawanie lub aktualizowanie rejestrów

1. Otwórz `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json` i wprowadź nowe wpisy
   lub zmodyfikuj istniejące.
2. Zadbaj o unikalność adresów i zachowanie posortowanej kolejności.
3. Uruchom test walidacyjny:

```bash
pytest tests/test_register_loader.py
```

4. (Opcjonalnie) wygeneruj moduł `registers.py` dla dodatkowych narzędzi:

```bash
python tools/generate_registers.py
```

5. Dołącz zmieniony plik JSON do commitu.

### Migracja z CSV na JSON

Pliki CSV zostały oznaczone jako przestarzałe i ich obsługa będzie
usunięta w przyszłych wersjach. Użycie pliku CSV zapisze ostrzeżenie w
logach. Aby ręcznie przekonwertować dane:

1. Otwórz dotychczasowy plik CSV z definicjami rejestrów.
2. Dla każdego wiersza utwórz obiekt w `custom_components/thessla_green_modbus/registers/thessla_green_registers_full.json`
   z polami `function`, `address_dec`, `address_hex`, `name`, `description` i `access`.
3. Zachowaj sortowanie adresów oraz format liczbowy (`0x` dla wartości hex).
4. Usuń lub zignoruj plik CSV i uruchom walidację jak przy dodawaniu nowych
   rejestrów.

## 📄 Licencja

MIT License - Zobacz [LICENSE](LICENSE) dla szczegółów.

## 🙏 Podziękowania

- **ThesslaGreen** za udostępnienie dokumentacji Modbus
- **Społeczność Home Assistant** za testy i feedback
- **Zespół pymodbus** za doskonałą bibliotekę Modbus

---

**🎉 Ciesz się inteligentną wentylacją z Home Assistant!** 🏠💨
