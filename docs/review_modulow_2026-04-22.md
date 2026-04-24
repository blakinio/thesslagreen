# Przegląd modułów krytycznych — stan na 2026-04-22

## 1) Zakres przeglądu (major modules in scope)

Przejrzane moduły o największym wpływie na runtime i utrzymanie:

1. `coordinator.py` (1217 linii)
2. `_coordinator_io.py` (782 linii)
3. `scanner/core.py` (1031 linii)
4. `modbus_transport.py` (891 linii)
5. `config_flow.py` (674 linii)
6. `registers/loader.py` (729 linii)
7. `services.py` (248 linii)

Weryfikacja rozmiarów wykonana skryptowo (`wc -l`) podczas tego przeglądu.

## 2) Ryzyka główne — jawna weryfikacja (verified / rejected)

### R1. Nadmierna złożoność i duże pliki
- **Status: VERIFIED**
- Uzasadnienie:
  - Koordynator scala wiele odpowiedzialności i miksinów oraz pozostaje bardzo duży.
  - Warstwa IO ma nadal znaczną objętość i duże metody batch/fallback.
  - Scanner core i transport pozostają dużymi „hubami” logiki.

### R2. Retry/disconnect/error handling może być niespójne między warstwami
- **Status: PARTIALLY VERIFIED**
- Uzasadnienie:
  - Widoczne są centralne elementy polityki błędów i retry.
  - Nadal istnieje kilka warstw z własną logiką retry/disconnect (transport, coordinator IO, scanner IO), co utrudnia pełną spójność behawioralną.

### R3. Brak maintainability guard w CI
- **Status: REJECTED**
- Uzasadnienie:
  - CI uruchamia `tools/check_maintainability.py`.
  - Skrypt ma zdefiniowane limity długości pliku/funkcji.

### R4. Rozbicie config flow i coordinator na moduły pomocnicze
- **Status: VERIFIED (wdrożone częściowo funkcjonalnie, ale nadal wysoka objętość plików wejściowych)**
- Uzasadnienie:
  - Oba moduły delegują do wielu helperów.
  - Mimo delegacji same pliki wejściowe nadal są duże, więc koszt nawigacji/utrzymania jest odczuwalny.

### R5. Ryzyko regresji przez mało czytelne testy scenariuszy edge-case
- **Status: PARTIALLY VERIFIED**
- Uzasadnienie:
  - Pokrycie scenariuszy awaryjnych jest szerokie.
  - Część testów była historycznie bardzo „mock-heavy”, co podnosi koszt utrzymania przy zmianach refaktorowych.

## 3) Dowody (evidence-based pointers)

- `coordinator.py` wykorzystuje miksiny + helpery, ale pozostaje głównym punktem orkiestracji.
- `_coordinator_io.py` zawiera rozbudowaną logikę odczytu batch/fallback/retry i obsługę rozłączeń.
- `scanner/core.py` agreguje wiele odpowiedzialności i re-eksportów scanner-domain.
- `modbus_transport.py` łączy abstrakcje transportu, błędy i retry/backoff.
- `config_flow.py` deleguje do wielu `config_flow_*`.
- CI uruchamia maintainability gate.
- `tools/check_maintainability.py` definiuje limity (`max_file_lines=1300`, `max_function_lines=260`).

## 4) Rekomendacje (priorytety i działania)

## P0 (najbliżej): redukcja ryzyka przy minimalnym koszcie
1. **Wydzielić z `_coordinator_io.py` moduł `coordinator_read_batches.py`**
   - Przenieść `_read_input_registers_optimized`, `_read_holding_registers_optimized`, `_read_holding_individually`.
   - Zachować publiczne API mixina jako cienkie delegaty.
2. **Wydzielić z `scanner/core.py` moduł `scanner_runtime.py`**
   - Skupić w nim retry/backoff/call wrappers.
   - Ograniczyć `scanner/core.py` do kompozycji i re-eksportów.

## P1 (kolejny etap): standaryzacja błędów i retry
1. **Ujednolicić kontrakt error/retry między coordinator IO, scanner IO i transport**
   - Wspólne klasyfikowanie błędów transient/permanent.
   - Spójne logowanie attempt/backoff/reason.
2. **Dodać testy kontraktowe cross-layer**
   - Te same scenariusze timeout/cancel/connection reset odpalane dla warstw: transport/coordinator/scanner.

## P2 (utrzymanie długoterminowe)
1. **Zaostrzyć maintainability gate etapowo**
   - Najpierw monitorowanie (warning), potem twarde limity dla nowych/zmienianych plików.
2. **Wprowadzić checklistę PR dla dużych metod**
   - Wymagane: extraction plan + test impact + rollback plan.

## 5) Mapowanie findings -> implementation steps

1. **FINDING:** duże moduły IO/scanner nadal centralizują wiele odpowiedzialności.  
   **STEP:** extraction do `coordinator_read_batches.py` i `scanner_runtime.py` (P0).

2. **FINDING:** retry/disconnect nie jest jeszcze w 100% jednolite cross-layer.  
   **STEP:** wspólny kontrakt klasyfikacji błędów + testy kontraktowe (P1).

3. **FINDING:** gate istnieje, ale progi są relatywnie liberalne.  
   **STEP:** stopniowe zaostrzanie progów per changed-files (P2).

4. **FINDING:** config/coordinator są modularne, ale wejściowe pliki nadal duże.  
   **STEP:** kolejne extraction passy na największych metodach + utrzymanie cienkich fasad (P0/P1).

## 6) Postęp wdrożenia po tym przeglądzie

- Wydzielono retry/disconnect orchestration z `_coordinator_io.py` do nowego modułu
  `_coordinator_retry.py` (cienkie delegaty pozostawione w mixinie).
- Wydzielono batch-read logic z `_coordinator_io.py` do modułu
  `_coordinator_read_batches.py` (`read_input_registers_optimized`,
  `read_holding_registers_optimized`, `read_holding_individually`).
- Wydzielono coil/discrete batch-read logic z `_coordinator_io.py` do modułu
  `_coordinator_read_bits.py` (`read_coil_registers_optimized`,
  `read_discrete_inputs_optimized`).
- W `scanner/core.py` wydzielono normalizację jittera i inicjalizację kolekcji
  runtime do `scanner/setup.py` (`normalize_backoff_jitter`,
  `initialize_runtime_collections`), zmniejszając ciężar konstruktora klasy.
- W `scanner/core.py` wydzielono też kroki setupowe do `scanner/setup.py`:
  inicjalizację znanych brakujących adresów oraz ładowanie map rejestrów
  (`populate_known_missing_addresses`, `update_known_missing_addresses`,
  `async_setup_register_maps`).
- W `scanner/core.py` wydzielono budowanie transportów TCP/AUTO do
  `scanner/setup.py` (`build_tcp_transport`, `build_auto_tcp_attempts`),
  dzięki czemu logika doboru timeoutów i kolejności prób jest scentralizowana.
- W `scanner/core.py` wydzielono zamykanie transportu/klienta do helpera
  `async_close_connection` w `scanner/setup.py`, utrzymując klasę skanera jako
  cienką fasadę nad operacjami runtime.
- Wydzielono logikę selekcji i grupowania rejestrów z `scanner/core.py` do
  nowego modułu `scanner/selection.py` (`build_names_by_address`,
  `group_registers_for_batch_read`, `select_scan_registers`), aby ograniczyć
  objętość domenowej logiki w klasie skanera.
- Wydzielono współdzielone niskopoziomowe helpery odczytu koordynatora do
  `_coordinator_read_common.py` (`execute_read_call`, logika klasyfikacji
  odpowiedzi błędowych i retry log), a `_coordinator_io.py` pozostawiono jako
  warstwę delegującą.
- Wydzielono też ścieżkę obsługi błędów update koordynatora do
  `_coordinator_update_errors.py` (`handle_update_error`,
  `apply_update_failure_state`), co upraszcza `_coordinator_io.py` i centralizuje
  mutacje statystyk/stanu offline.
- Dodano `_coordinator_runtime_io.py` i wydzielono z `_coordinator_io.py`
  helpery runtime (`call_modbus`, `read_all_register_data`), aby dalej odchudzić
  miksin i ujednolicić delegowanie ścieżek wejścia/odczytu.
- Finalnie rozdzielono warstwę koordynatora do końca: `_ModbusIOMixin`
  przeniesiono do `_coordinator_io_mixin.py`, a `_coordinator_io.py` pełni już
  wyłącznie rolę kompatybilnej fasady/re-exportu.
- W `scanner/core.py` wydzielono modułowe helpery runtime do `scanner/io_runtime.py`
  (bootstrap `pymodbus.client`, retry-yield/backoff, `call_modbus_with_fallback`)
  oraz helpery map rejestrów do `scanner/register_map_runtime.py`, dalszym
  krokiem odciążając core do roli fasady.
- Dodatkowo wydzielono fabrykę tworzenia skanera do `scanner/setup.py`
  (`async_create_scanner_instance`), a `ThesslaGreenDeviceScanner.create()`
  deleguje już wyłącznie parametry i zależności.
- Wydzielono też metody odczytu (read API) z klasy skanera do mixina
  `scanner/read_facade.py` (`ScannerReadFacadeMixin`), żeby dalej zmniejszyć
  objętość `scanner/core.py` i utrzymać go jako warstwę kompozycji.
- Wydzielono również operacje capability do mixina
  `scanner/capabilities_facade.py` (`ScannerCapabilitiesFacadeMixin`), przenosząc
  walidację wartości i zarządzanie unsupported-ranges poza `scanner/core.py`.
- W `coordinator.py` wydzielono obsługę full-list i scan-cache do
  `_coordinator_scan_cache.py` (`load_full_register_list`,
  `normalise_*`, `apply_scan_cache`, `firmware_lacks_known_missing`,
  `store_scan_cache`), zmniejszając objętość logiki domenowej klasy.
- Po uruchomieniu pełniejszych testów przywrócono kompatybilność fasad:
  re-export `_PermanentModbusError` w `_coordinator_io.py` oraz patchowalne
  ścieżki transportu/modbus-call w scanner runtime helpers.
- Wydzielono obliczanie grup rejestrów z `coordinator.py` do
  `_coordinator_register_groups.py` (`compute_register_groups`), co dodatkowo
  odchudza klasę koordynatora.
- Wydzielono też auto-detekcję transportu TCP/RTU-over-TCP z `coordinator.py`
  do `_coordinator_transport_select.py` (`select_auto_transport`), zostawiając
  w klasie koordynatora cienką delegację i przypisanie wyniku.
- W testach scenariusze transport-less retry zostały doprecyzowane jako osobne,
  czytelne przypadki: przywrócenie klienta oraz propagacja błędu disconnect.

- Wydzielono helpery ścieżki połączenia z `coordinator.py` do
  `_coordinator_connection.py` (`reconnect_client_if_needed`,
  `build_rtu_transport`), redukując złożoność `_ensure_connected`.

- Wydzielono również normalizację konfiguracji init z `coordinator.py` do
  `_coordinator_init.py` (`normalize_runtime_config`), co skraca konstruktor
  i centralizuje przygotowanie `CoordinatorConfig` na starcie.

- Wydzielono sekwencję testu połączenia z `coordinator.py` do
  `_coordinator_connection_test.py` (`run_connection_test`), dzięki czemu
  `_test_connection` w klasie koordynatora pełni rolę lekkiej fasady.

- W `config_flow.py` wydzielono walidację i skan urządzenia do
  `config_flow_device_validation.py` (`validate_input_impl`), a
  `validate_input` pozostawiono jako cienką fasadę delegującą.

- W `config_flow.py` wydzielono też obsługę submitu reauth do
  `config_flow_reauth.py` (`process_reauth_submission`), dzięki czemu
  `async_step_reauth` ma prostszy przepływ sterowania.

- Z `config_flow.py` wydzielono również finalizację reauth confirm do
  `config_flow_reauth_confirm.py` (`apply_reauth_update`), upraszczając
  `async_step_reauth_confirm` do delegacji i obsługi wyniku.

- Wydzielono również submit kroku user z `config_flow.py` do
  `config_flow_user_submit.py` (`process_user_submission`), dzięki czemu
  `async_step_user` został uproszczony do delegacji i obsługi stanu.

- Wydzielono aplikację wyniku skanu urządzenia z `coordinator.py` do
  `_coordinator_scan_result.py` (`apply_scan_result`), upraszczając
  `_apply_scan_result` do delegacji i zmniejszając sprzężenie klasy.

- Wydzielono budowanie kwargs dla factory skanera z `coordinator.py` do
  `_coordinator_scanner_kwargs.py` (`build_scanner_kwargs`), aby uprościć
  `_build_scanner_kwargs` i odseparować mapowanie konfiguracji runtime.

- Wydzielono też fabrykę konfiguracji `from_params` z `coordinator.py` do
  `_coordinator_factory.py` (`build_config_from_params`), ograniczając
  duplikację mapowania argumentów do `CoordinatorConfig`.

- Dodano wspólny kontrakt klasyfikacji błędów/retry w `error_contract.py`
  (`classify_error`, `log_retry_attempt`) i podłączono go do warstw
  coordinator/transport/scanner przez lekkie adaptery klasyfikacji.
- Zaostrzono maintainability gate w `tools/check_maintainability.py`
  przez strictejsze limity per-path dla kluczowych modułów
  (`coordinator.py`, `config_flow.py`, `modbus_transport.py`, `registers/loader.py`)
  przy zachowaniu bezpiecznych globalnych progów domyślnych.
- Dodano checklistę i zasady refaktoru do `docs/refactor_guidelines.md`
  (kiedy ekstrahować funkcję/moduł i kiedy dodawać test kontraktowy cross-layer).

- W `registers/loader.py` wydzielono pomocnicze kroki parsera
  (`_normalise_enum_map`, `_coerce_scaling_fields`, `_register_from_parsed`)
  i uproszczono `_parse_registers` do iteracji po jasno nazwanych etapach.
- Kontynuowano extraction pass w `registers/loader.py` przez rozbicie
  złożonych ścieżek `RegisterDef.decode`/`encode` na mniejsze helpery
  (`_decode_multi_register`, `_decode_single_register`,
  `_encode_multi_register`, `_coerce_scaled_input`, `_apply_output_scaling`)
  bez zmiany kontraktu publicznego klasy `RegisterDef`.
- W `modbus_transport.py` wydzielono pomocniczą warstwę retry do
  `_transport_retry.py` (`log_transport_retry`, `apply_transport_backoff`),
  pozostawiając `BaseModbusTransport` jako cienki orchestrator.
- W `modbus_transport.py` dodano wspólną klasę `_ClientBackedTransport`,
  która centralizuje lifecycle klienta (`_ensure_client`, `_connect_client`,
  `_reset_connection`) oraz delegaty read/write dla transportów TCP/RTU,
  redukując duplikację metod pomiędzy `TcpModbusTransport` i
  `RtuModbusTransport`.
- W `RawRtuOverTcpTransport` wydzielono wspólne helpery
  (`_decode_register_words`, `_validate_write_echo`,
  `_read_registers_common`), upraszczając pary metod read/write
  i usuwając powieloną walidację odpowiedzi.
- Dodano jawne adaptery logowania retry per warstwa:
  `log_coordinator_retry` (`_coordinator_retry.py`) oraz
  `log_scanner_retry` (`scanner/io.py` + adapter w `scanner/io_runtime.py`),
  aby ujednolicić kontrakt retry logging cross-layer.
- Rozszerzono test kontraktowy cross-layer (`tests/test_error_contract.py`)
  o macierz wyjątków (timeout/cancelled/connection/permanent), aby wymusić
  spójność klasyfikacji we wszystkich warstwach.
- Rozszerzono też test kontraktowy o retry logging cross-layer
  (coordinator/scanner/transport), weryfikując spójny format
  `layer=...` / `reason=...` w logach.
- Zaostrzono limity maintainability per-path dla
  `modbus_transport.py` i `registers/loader.py` w
  `tools/check_maintainability.py` (etapowe dociążanie bramki jakości).
- Dalsze zaostrzenie gate: dodano per-path limity również dla
  `scanner/io.py` i `scanner/core.py`.
- Kolejny extraction pass w `coordinator.py`: wydzielono lifecycle skanu
  i ostrzeżenia braków device-info do `_coordinator_device_info.py`
  (`run_device_scan`, `warn_missing_device_info`), upraszczając metody
  `_run_device_scan` i `_warn_missing_device_info` do cienkich delegatów.
- Kolejny extraction pass w ścieżce połączenia: wydzielono bezpośredni
  connect klienta TCP do `_coordinator_connection.py`
  (`connect_direct_tcp_client`) i zredukowano logikę w
  `_try_direct_client_connect` w `coordinator.py` do delegacji.
- Dalsza redukcja odpowiedzialności `coordinator.py`: wydzielono budowanie
  transportu TCP/RTU-over-TCP do `_coordinator_connection.py`
  (`build_tcp_transport`) i sprowadzono `_build_tcp_transport` do delegatu.
- Kolejny extraction pass w setupie połączenia: wydzielono obsługę
  wyjątków setupu klienta do `_coordinator_connection.py`
  (`setup_client_with_retry`), a `_async_setup_client` w `coordinator.py`
  został zredukowany do delegacji.
- Kolejny extraction pass w `_ensure_connected`: wydzielono selekcję/budowę
  transportu do `_coordinator_connection.py` (`ensure_transport_selected`),
  co ograniczyło branching transportowy w `coordinator.py`.
- Wydzielono też finalny krok łączenia transport/klient do helpera
  `_coordinator_connection.py` (`connect_transport_or_client`), aby
  uprościć główną ścieżkę `_ensure_connected`.
