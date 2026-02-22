#!/usr/bin/env python3
"""Translate description_en fields in thessla_green_registers_full.json from Polish to English.

Applies a comprehensive phrase-substitution dictionary built from the full set of
Polish descriptions found in the register file.  Every entry whose ``description_en``
is identical to its Polish ``description`` (i.e. not yet translated) is updated in
place.  Entries that cannot be matched by the dictionary are left with a ``[TODO]``
prefix so they can be reviewed manually.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REGISTER_FILE = ROOT / "custom_components" / "thessla_green_modbus" / "registers" / "thessla_green_registers_full.json"

# ---------------------------------------------------------------------------
# Polish → English translation table.
# Keys are full Polish strings or significant sub-phrases (applied in order).
# Longer / more specific entries must appear BEFORE shorter overlapping ones.
# ---------------------------------------------------------------------------
FULL_TRANSLATIONS: dict[str, str] = {
    # ---- Date / time ----
    "Data i godzina - liczba dziesiątek / jedności roku i miesiąc [RRMM]": "Date and time - tens/units of year and month [YYMM]",
    "Data i godzina - dzień miesiąca i dzień tygodnia [DDTT]": "Date and time - day of month and day of week [DDWW]",
    "Data i godzina - godzina i minuta [GGmm]": "Date and time - hour and minute [HHmm]",
    "Data i godzina - sekunda i setne części sekundy [sscc]": "Date and time - second and hundredths of a second [sscc]",
    "Data zablokowania centrali kluczem produktu - liczba dziesiątek / jedności roku [00RR]": "Product key lock date - tens/units of year [00YY]",
    "Data zablokowania centrali kluczem produktu - miesiąc [00MM]": "Product key lock date - month [00MM]",
    "Data zablokowania centrali kluczem produktu - dzień [00DD]": "Product key lock date - day [00DD]",
    "Data kompilacji oprogramowania Basic": "Firmware Basic compilation date",
    "Godzina kompilacji oprogramowania Basic": "Firmware Basic compilation time",
    "Godzina i minuta rozpoczęcia automatycznej procedury kontroli filtrów [GGMM]": "Filter auto-check procedure start time [HHmm]",
    "Godzina i minuta rozpoczęcia regeneracji latem [GGMM] w przypadku regeneracji dobowej (harmonogram)": "GWC regeneration start time in summer [HHmm] (daily schedule)",
    "Godzina i minuta rozpoczęcia regeneracji zimą [GGMM] w przypadku regeneracji dobowej (harmonogram)": "GWC regeneration start time in winter [HHmm] (daily schedule)",
    "Godzina i minuta zakończenia regeneracji latem [GGMM] w przypadku regeneracji dobowej (harmonogram)": "GWC regeneration end time in summer [HHmm] (daily schedule)",
    "Godzina i minuta zakończenia regeneracji zimą [GGMM] w przypadku regeneracji dobowej (harmonogram)": "GWC regeneration end time in winter [HHmm] (daily schedule)",
    "Godzina rozpoczęcia wietrzenia w trybie MANUALNYM [GGMM]": "Manual airing start time [HHmm]",
    "Dane kalibracyjne zegara czasu rzeczywistego": "Real-time clock calibration data",
    "Bieżący dzień tygodnia dla trybu automatycznego": "Current day of week for automatic mode",
    "Bieżący odcinek czasowy dla trybu automatycznego": "Current time slot for automatic mode",

    # ---- Firmware / version ----
    "Główna wersja oprogramowania": "Firmware major version",
    "Wersja poboczna oprogramowania": "Firmware minor version",
    "Wersja poprawki oprogramowania": "Firmware patch version",
    "Wersja oprogramowania modułu CF lub (od 4.75) TG-02": "CF module (or TG-02 from v4.75) firmware version",

    # ---- Serial number ----
    "Numer seryjny sterownika": "Controller serial number",

    # ---- Coil / relay output states ----
    "Stan wyjścia przekaźnika pompy obiegowej nagrzewnicy": "Duct water heater circulation pump relay output state",
    "Stan wyjścia siłownika przepustnicy bypass": "Bypass damper actuator output state",
    "Stan wyjścia sygnału potwierdzenia pracy centrali (O1)": "AHU confirmation signal output state (O1)",
    "Stan wyjścia przekaźnika zasilania wentylatorów": "Fan power supply relay output state",
    "Stan wyjścia przekaźnika zasilania kabla grzejnego": "Heating cable power relay output state",
    "Stan wyjścia przekaźnika potwierdzenia pracy (Expansion)": "Expansion module operation confirmation relay output state",
    "Stan wyjścia przekaźnika GWC": "GWC relay output state",
    "Stan wyjścia zasilającego przepustnicę okapu": "Hood damper power supply output state",

    # ---- Discrete input states ----
    "Stan wejścia zabezpieczenia termicznego elektrycznej nagrzewnicy kanałowej": "Duct electric heater thermal protection input state",
    "Komunikacja z modułem Expansion": "Expansion module communication state",
    "Stan wejścia presostatu filtra kanałowego": "Duct filter differential pressure switch input state",
    "Stan wejścia włącznika funkcji OKAP": "Hood function switch input state",
    "Stan wejścia dwustanowego czujnika jakości powietrza": "Binary air quality sensor input state",
    "Stan wejścia dwustanowego czujnika wilgotności": "Binary humidity sensor input state",
    "Stan wejścia włącznika funkcji WIETRZENIE": "Airing function switch input state",
    "Stan wejścia przełącznika AirS w pozycji \"Wietrzenie\"": "AirS panel switch input state – Airing position",
    "Stan wejścia przełącznika AirS w pozycji \"3 bieg\"": "AirS panel switch input state – Speed 3 position",
    "Stan wejścia przełącznika AirS w pozycji \"2 bieg\"": "AirS panel switch input state – Speed 2 position",
    "Stan wejścia przełącznika AirS w pozycji \"1 bieg\"": "AirS panel switch input state – Speed 1 position",
    "Stan wejścia włącznika funkcji KOMINEK": "Fireplace function switch input state",
    "Stan wejścia sygnału alarmu pożarowego (P.POZ.)": "Fire alarm signal input state (F.FIRE.)",
    "Stan wejścia presostatu filtrów w rekuperatorze (DP1)": "AHU filter differential pressure switch input state (DP1)",
    "Stan wejścia zabezpieczenia termicznego nagrzewnicy systemu przeciwzamrożeniowego FPX": "FPX anti-freeze heater thermal protection input state",
    "Stan wejścia sygnału załączenia funkcji PUSTY DOM": "Empty house function activation signal input state",

    # ---- Temperatures ----
    "Temperatura powietrza zewnętrznego (TZ1)": "Outdoor air temperature (TZ1)",
    "Temperatura powietrza nawiewanego (TN1)": "Supply air temperature (TN1)",
    "Temperatura powietrza usuwanego z pomieszczenia (TP)": "Exhaust air temperature (TP)",
    "Temperatura powietrza za nagrzewnicą FPX (TZ2)": "Air temperature after FPX anti-freeze heater (TZ2)",
    "Temperatura powietrza za nagrzewnicą / chłodnicą kanałową (TN2)": "Air temperature after duct heater/cooler (TN2)",
    "Temperatura przed wymiennikiem systemu glikolowego GWC (TZ3)": "Air temperature before glycol GWC heat exchanger (TZ3)",
    "Temperatura otoczenia (TO)": "Ambient temperature (TO)",
    "Temperatura nagrzewnicy (TH)": "Heater temperature (TH)",
    "Temperatura aktywacji działania bypass w funkcji grzania (freeheating)": "Bypass activation temperature for free heating function",
    "Temperatura aktywacji działania bypass w funkcji chłodzenia (freecooling)": "Bypass activation temperature for free cooling function",
    "Minimalna temperatura powietrza zewnętrznego warunkująca załączenie bypass": "Minimum outdoor air temperature required to activate bypass",
    "Dolny próg temperatury załączenia funkcji GWC": "Lower temperature threshold for GWC activation",
    "Górny próg temperatury załączenia funkcji GWC": "Upper temperature threshold for GWC activation",
    "Temperatura powietrza usuwanego z pomieszczeń wyższa od maksymalnej": "Exhaust air temperature above maximum limit",
    "Zbyt wysoka temperatura przed rekuperatorem": "Air temperature before heat exchanger too high",
    "Temperatura zadana trybu KOMFORT": "Comfort mode target temperature",
    "Zadana temperatura nawiewu - tryb MANUALNY": "Supply air temperature setpoint – manual mode",
    "Zadana temperatura nawiewu - tryb CHWILOWY": "Supply air temperature setpoint – temporary mode",

    # ---- Flow rates / ventilation intensity ----
    "Zadana intensywność wentylacji (nawiew)": "Ventilation intensity setpoint (supply)",
    "Zadana intensywność wentylacji (nawiew) dla bypass działającego w trybie 2 lub 3": "Ventilation intensity setpoint (supply) for bypass mode 2 or 3",
    "Zadany strumień przepływu (nawiew)": "Supply airflow rate setpoint",
    "Zadany strumień przepływu (wywiew)": "Exhaust airflow rate setpoint",
    "Wartość chwilowa strumienia powietrza - nawiew": "Instantaneous supply airflow rate",
    "Wartość chwilowa strumienia powietrza - wywiew": "Instantaneous exhaust airflow rate",
    "Nominalny strumień powietrza nawiewanego dla działającego GWC powietrznego (typ 1)": "Nominal supply airflow rate with active air-type GWC (type 1)",
    "Nominalny strumień powietrza wywiewanego dla działającego GWC powietrznego (typ 1)": "Nominal exhaust airflow rate with active air-type GWC (type 1)",
    "Nominalny strumień powietrza nawiewanego": "Nominal supply airflow rate",
    "Nominalny strumień powietrza wywiewanego": "Nominal exhaust airflow rate",
    "Maksymalna możliwa do ustawienia intensywność wentylacji (nawiew)": "Maximum settable ventilation intensity (supply)",
    "Maksymalna możliwa do ustawienia intensywność wentylacji (wywiew)": "Maximum settable ventilation intensity (exhaust)",
    "Maksymalna możliwa do ustawienia intensywność wentylacji dla instalacji z GWC (nawiew)": "Maximum settable ventilation intensity for GWC installation (supply)",
    "Maksymalna możliwa do ustawienia intensywność wentylacji dla instalacji z GWC (wywiew)": "Maximum settable ventilation intensity for GWC installation (exhaust)",
    "Maksymalna możliwa do ustawienia intensywność wentylacji": "Maximum settable ventilation intensity",
    "Minimalna możliwa do ustawienia intensywność wentylacji": "Minimum settable ventilation intensity",
    "Intensywność wentylacji - tryb MANUALNY": "Ventilation intensity – manual mode",
    "Intensywność wentylacji - tryb CHWILOWY": "Ventilation intensity – temporary mode",
    "Intensywność wentylacji dla funkcji OKAP (nawiew)": "Ventilation intensity for hood function (supply)",
    "Intensywność wentylacji dla funkcji OKAP (wywiew)": "Ventilation intensity for hood function (exhaust)",
    "Intensywność wentylacji dla funkcji OTWARTE OKNA (wywiew)": "Ventilation intensity for open window function (exhaust)",
    "Intensywność wentylacji dla funkcji PUSTY DOM": "Ventilation intensity for empty house function",
    "Intensywność wentylacji dla funkcji WIETRZENIE - Funkcja specjalna nr: 3, 4": "Ventilation intensity for airing function – special function No. 3, 4",
    "Intensywność wentylacji dla funkcji WIETRZENIE - Funkcja specjalna nr: 3, 4, 5 (łazienka)": "Ventilation intensity for airing function – special function No. 3, 4, 5 (bathroom)",
    "Intensywność wentylacji dla funkcji WIETRZENIE - Funkcja specjalna nr: 6 (usuwanie zanieczyszczeń)": "Ventilation intensity for airing function – special function No. 6 (pollutant removal)",
    "Intensywność wentylacji dla funkcji WIETRZENIE - Funkcja specjalna nr: 7, 8, 9 (pokoje)": "Ventilation intensity for airing function – special function No. 7, 8, 9 (rooms)",

    # ---- Fan speed coefficients ----
    "Nastawa intensywności wentylacji - \"1 bieg\" - panel AirS": "Ventilation intensity setpoint – speed 1 – AirS panel",
    "Nastawa intensywności wentylacji - \"2 bieg\" - panel AirS": "Ventilation intensity setpoint – speed 2 – AirS panel",
    "Nastawa intensywności wentylacji - \"3 bieg\" - panel AirS": "Ventilation intensity setpoint – speed 3 – AirS panel",

    # ---- PWM / DAC ----
    "Napięcie sterujące wentylatorem nawiewnym (PWM)": "Supply fan control voltage (PWM)",
    "Napięcie sterujące wentylatorem wywiewnym (PWM)": "Exhaust fan control voltage (PWM)",
    "Napięcie sterujące nagrzewnicą kanałową (PWM)": "Duct heater control voltage (PWM)",
    "Napięcie sterujące chłodnicą kanałową (PWM)": "Duct cooler control voltage (PWM)",

    # ---- Operating modes ----
    "Tryb pracy AirPack - równorzędny z 0x1130": "AirPack operating mode – equivalent to 0x1130",
    "Tryb pracy AirPack - równorzędny z 0x1133": "AirPack operating mode – equivalent to 0x1133",
    "Tryb pracy AirPack": "AirPack operating mode",
    "Tryby specjalne pracy centrali": "AHU special operating modes",
    "Wybór harmonogramu - tryb AUTOMATYCZNY": "Schedule selection – automatic mode",
    "Wybór trybu pracy AirPack - EKO / KOMFORT": "AirPack operating mode selection – ECO / COMFORT",
    "Aktualny status trybu KOMFORT": "Current COMFORT mode status",
    "Tryb pracy / sposób realizacji funkcji bypass": "Bypass function operating mode / method",
    "Tryb działania systemu FPX": "FPX system operating mode",

    # ---- Bypass ----
    "Dezaktywacja działania bypass": "Bypass deactivation",
    "Aktualny status bypass": "Current bypass status",
    "Różnicowanie strumieni (wywiew < nawiew) dla bypass działającego w trybie 2": "Airflow differentiation (exhaust < supply) for bypass operating in mode 2",
    "Różnicowanie strumieni dla funkcji KOMINEK": "Airflow differentiation for fireplace function",

    # ---- GWC ----
    "Dezaktywacja działania GWC": "GWC deactivation",
    "Aktualny status działania GWC": "Current GWC operating status",
    "Wybór typu regeneracji złoża GWC": "GWC bed regeneration type selection",
    "Czas trwania regeneracji złoża GWC dla regeneracji temperaturowej": "GWC bed regeneration duration for temperature-based regeneration",
    "Różnica temperatur warunkująca załączenie regeneracji temperaturowej złoża GWC": "Temperature differential required to activate GWC bed temperature regeneration",
    "Flaga informująca o aktywnym trybie regeneracji złoża GWC": "Flag indicating active GWC bed regeneration mode",

    # ---- Special functions / timing ----
    "Funkcje specjalne": "Special functions",
    "Czas działania funkcji KOMINEK": "Fireplace function operating time",
    "Czas działania funkcji WIETRZENIE - Funkcja specjalna nr: 3 (łazienka)": "Airing function operating time – special function No. 3 (bathroom)",
    "Czas działania funkcji WIETRZENIE - Funkcja specjalna nr: 7, 8, 9 (pokoje)": "Airing function operating time – special function No. 7, 8, 9 (rooms)",
    "Opóźnienie załączenia funkcji WIETRZENIE - Funkcja specjalna nr: 4 (łazienka)": "Airing function switch-on delay – special function No. 4 (bathroom)",
    "Opóźnienie wyłączenia funkcji WIETRZENIE - Funkcja specjalna nr: 4 (łazienka)": "Airing function switch-off delay – special function No. 4 (bathroom)",

    # ---- Filter / access / lock ----
    "Poziom dostępu": "Access level",
    "System kontroli filtrów / typ filtrów": "Filter control system / filter type",
    "Dzień tygodnia, w którym przeprowadzana będzie procedura automatycznej kontroli filtrów": "Day of week for the automatic filter check procedure",
    "Sygnalizacja konieczności wymiany filtra kanałowego": "Duct filter replacement required indication",
    "Sygnalizacja konieczności wymiany filtrów w centrali nie wyposażonej w presostat": "AHU filter replacement required indication (unit without pressure switch)",
    "Sygnalizacja konieczności wymiany filtrów w centrali wyposażonej w presostat": "AHU filter replacement required indication (unit with pressure switch)",
    "Sygnalizacja konieczności wprowadzenia klucza produktu centrali wentylacyjnej AirPack": "AirPack product key entry required indication",
    "Sygnalizacja konieczności wprowadzenia klucza produktu": "Product key entry required indication",

    # ---- Modbus UART settings ----
    "Nastawy komunikacji Modbus - port Air++ ID urządzenia": "Modbus communication settings – Air++ port device ID",
    "Nastawy komunikacji Modbus - port Air++ Szybkość transmisji": "Modbus communication settings – Air++ port baud rate",
    "Nastawy komunikacji Modbus - port Air++ Parzystość": "Modbus communication settings – Air++ port parity",
    "Nastawy komunikacji Modbus - port Air++ Bity stopu": "Modbus communication settings – Air++ port stop bits",
    "Nastawy komunikacji Modbus - port Air-B ID urządzenia": "Modbus communication settings – Air-B port device ID",
    "Nastawy komunikacji Modbus - port Air-B Szybkość transmisji": "Modbus communication settings – Air-B port baud rate",
    "Nastawy komunikacji Modbus - port Air-B Parzystość": "Modbus communication settings – Air-B port parity",
    "Nastawy komunikacji Modbus - port Air-B Bity stopu": "Modbus communication settings – Air-B port stop bits",

    # ---- Reset / control ----
    "Reset ustawień trybów pracy": "Operating mode settings reset",
    "Reset ustawień użytkownika": "User settings reset",
    "ON / OFF - załączanie urządzenia": "ON / OFF – device power control",
    "Kod alarmu zatrzymującego pracę AirPack": "AirPack shutdown alarm code",
    "Centrala zatrzymana z panelu Air+ lub AirL+, Air++ lub AirMobile": "AHU stopped from Air+, AirL+, Air++ or AirMobile panel",
    "Centrala zatrzymana z panelu AirS": "AHU stopped from AirS panel",

    # ---- Alarms / errors / status flags ----
    "Alarmy - Flaga informująca o wystąpieniu błędu - alarm \"S\"": "Alarms – error occurrence flag – \"S\" alarm",
    "Alarmy - Flaga informująca o wystąpieniu ostrzeżenia - alarm \"E\"": "Alarms – warning occurrence flag – \"E\" alarm",
    "Flagi błędów E196-E199": "Error flags E196–E199",
    "Nie działa wentylator nawiewny": "Supply fan not operating",
    "Nie działa wentylator wywiewny": "Exhaust fan not operating",
    "Nie zadziałało zabezpieczenie przeciwzamrożeniowe wymiennika rekuperacyjnego (FPX)": "Heat exchanger anti-freeze protection (FPX) did not activate",
    "Nie został wymieniony filtr kanałowy": "Duct filter not replaced",
    "Nie zostały wymienione filtry w centrali (w przypadku centrali nie wyposażonej w presostat)": "AHU filters not replaced (unit without pressure switch)",
    "Nie zostały wymienione filtry w centrali (w przypadku centrali wyposażonej w presostat)": "AHU filters not replaced (unit with pressure switch)",
    "Zabezpieczenie przeciwzamrożeniowe nagrzewnicy wodnej nie przyniosło oczekiwanych rezultatów": "Water heater anti-freeze protection did not achieve expected results",
    "Zabezpieczenie przeciwzamrożeniowe nagrzewnicy wodnej zadziałało maksymalną ilość razy": "Water heater anti-freeze protection activated maximum number of times",
    "Zabezpieczenie termiczne nagrzewnicy FPX zadziałało maksymalną ilość razy w określonym czasie": "FPX heater thermal protection activated maximum number of times within the specified period",
    "Zadziałał czujnik PPOŻ": "Fire protection sensor activated",
    "Zadziałało zabezpieczenie termiczne nagrzewnicy elektrycznej w centrali przy aktywnym systemie FPX": "AHU electric heater thermal protection activated while FPX system is active",
    "Zbyt wysoka temperatura przed rekuperatorem": "Air temperature before heat exchanger too high",
    "Brak komunikacji z modułem Expansion": "No communication with Expansion module",
    "Brak komunikacji z modułem TG-02": "No communication with TG-02 module",
    "Brak możliwości kalibracji urządzenia ze względu na zbyt niską temperaturę powietrza zewnętrznego": "Device calibration not possible due to outdoor air temperature too low",
    "Brak odczytu z czujnika temperatury powietrza zewnętrznego - CZERPNIA (TZ1)": "No reading from outdoor air temperature sensor – air intake (TZ1)",
    "Brak odczytu z czujnika temperatury powietrza nawiewanego - NAWIEW (TN1)": "No reading from supply air temperature sensor – supply (TN1)",
    "Brak odczytu z czujnika temperatury powietrza usuwanego z pomieszczeń - WYWIEW (TP)": "No reading from exhaust air temperature sensor – exhaust (TP)",
    "Brak odczytu z czujnika temperatury powietrza na wlocie do wymiennika rekuperacyjnego - FPX (TZ2)": "No reading from temperature sensor at heat exchanger inlet – FPX (TZ2)",
    "Brak odczytu z czujnika temperatury powietrza nawiewanego za wymiennikiem kanałowym (TN2)": "No reading from supply air temperature sensor after duct heat exchanger (TN2)",
    "Brak odczytu z czujnika temperatury powietrza w pomieszczeniu, w którym jest zamontowana centrala (TO)": "No reading from room temperature sensor where AHU is installed (TO)",
    "Brak odczytu z czujnika temperatury powietrza zewnętrznego glikolowego GWC (TZ3)": "No reading from glycol GWC outdoor air temperature sensor (TZ3)",
    "Awaria czujnika CF wentylatora nawiewnego - Brak komunikacji z przetwornikiem ciśnienia wentylatora": "Supply fan CF sensor failure – no communication with fan pressure transducer",
    "Awaria czujnika CF wentylatora wywiewnego - Brak komunikacji z przetwornikiem ciśnienia wentylatora": "Exhaust fan CF sensor failure – no communication with fan pressure transducer",
    "Błąd komunikacji I2C": "I2C communication error",
    "Nie zadziałało zabezpieczenie przeciwzamrożeniowe wymiennika rekuperacyjnego (FPX)": "Heat exchanger anti-freeze protection (FPX) did not activate",
    "Uszkodzony czujnik temperatury powietrza zewnętrznego": "Outdoor air temperature sensor damaged",
    "Uszkodzony czujnik temperatury powietrza zewnętrznego oraz czujnik temperatury powietrza dla glikolowego GWC": "Outdoor air temperature sensor and glycol GWC temperature sensor damaged",
    "Uszkodzony czujnik temperatury powietrza na wlocie do wymiennika rekuperacyjnego przy temperaturze powietrza zewnętrznego stanowiącej warunki do zadziałania systemu FPX": "Temperature sensor at heat exchanger inlet damaged while outdoor temp conditions require FPX activation",
    "Uszkodzony czujnik temperatury powietrza w kanale nawiewnym za nagrzewnicą wodną": "Temperature sensor in supply duct after water heater damaged",

    # ---- FPX ----
    "Flaga uruchomienia systemu FPX": "FPX system activation flag",
    "Flaga wymuszenia / aktywacji trybu CHWILOWEGO - zmiana intensywności wentylacji": "Temporary mode force/activation flag – ventilation intensity change",
    "Flaga wymuszenia / aktywacji trybu CHWILOWEGO - zmiana wartości zadanej temperatury nawiewu": "Temporary mode force/activation flag – supply air temperature setpoint change",

    # ---- Constant Flow / misc ----
    "Status aktywności systemu Constant Flow": "Constant Flow system active status",
    "Status działania procedury HEWR": "HEWR procedure operating status",
    "Wybór języka panelu Air++": "Air++ panel language selection",

    # ---- Schedule – SUMMER (LATO) ----
    "LATO - Poniedziałek - 1": "SUMMER – Monday – slot 1",
    "LATO - Poniedziałek - 1 [AATT]": "SUMMER – Monday – slot 1 [intensity/temp]",
    "LATO - Poniedziałek - 2": "SUMMER – Monday – slot 2",
    "LATO - Poniedziałek - 2 [AATT]": "SUMMER – Monday – slot 2 [intensity/temp]",
    "LATO - Poniedziałek - 3": "SUMMER – Monday – slot 3",
    "LATO - Poniedziałek - 3 [AATT]": "SUMMER – Monday – slot 3 [intensity/temp]",
    "LATO - Poniedziałek - 4": "SUMMER – Monday – slot 4",
    "LATO - Poniedziałek - 4 [AATT]": "SUMMER – Monday – slot 4 [intensity/temp]",
    "LATO - Poniedziałek - Wietrzenie [GGMM]": "SUMMER – Monday – airing time [HHmm]",
    "LATO - Wtorek - 1": "SUMMER – Tuesday – slot 1",
    "LATO - Wtorek - 1 [AATT]": "SUMMER – Tuesday – slot 1 [intensity/temp]",
    "LATO - Wtorek - 2": "SUMMER – Tuesday – slot 2",
    "LATO - Wtorek - 2 [AATT]": "SUMMER – Tuesday – slot 2 [intensity/temp]",
    "LATO - Wtorek - 3": "SUMMER – Tuesday – slot 3",
    "LATO - Wtorek - 3 [AATT]": "SUMMER – Tuesday – slot 3 [intensity/temp]",
    "LATO - Wtorek - 4": "SUMMER – Tuesday – slot 4",
    "LATO - Wtorek - 4 [AATT]": "SUMMER – Tuesday – slot 4 [intensity/temp]",
    "LATO - Wtorek - Wietrzenie [GGMM]": "SUMMER – Tuesday – airing time [HHmm]",
    "LATO - Środa - 1": "SUMMER – Wednesday – slot 1",
    "LATO - Środa - 1 [AATT]": "SUMMER – Wednesday – slot 1 [intensity/temp]",
    "LATO - Środa - 2": "SUMMER – Wednesday – slot 2",
    "LATO - Środa - 2 [AATT]": "SUMMER – Wednesday – slot 2 [intensity/temp]",
    "LATO - Środa - 3": "SUMMER – Wednesday – slot 3",
    "LATO - Środa - 3 [AATT]": "SUMMER – Wednesday – slot 3 [intensity/temp]",
    "LATO - Środa - 4": "SUMMER – Wednesday – slot 4",
    "LATO - Środa - 4 [AATT]": "SUMMER – Wednesday – slot 4 [intensity/temp]",
    "LATO - Środa - Wietrzenie [GGMM]": "SUMMER – Wednesday – airing time [HHmm]",
    "LATO - Czwartek - 1": "SUMMER – Thursday – slot 1",
    "LATO - Czwartek - 1 [AATT]": "SUMMER – Thursday – slot 1 [intensity/temp]",
    "LATO - Czwartek - 2": "SUMMER – Thursday – slot 2",
    "LATO - Czwartek - 2 [AATT]": "SUMMER – Thursday – slot 2 [intensity/temp]",
    "LATO - Czwartek - 3": "SUMMER – Thursday – slot 3",
    "LATO - Czwartek - 3 [AATT]": "SUMMER – Thursday – slot 3 [intensity/temp]",
    "LATO - Czwartek - 4": "SUMMER – Thursday – slot 4",
    "LATO - Czwartek - 4 [AATT]": "SUMMER – Thursday – slot 4 [intensity/temp]",
    "LATO - Czwartek - Wietrzenie [GGMM]": "SUMMER – Thursday – airing time [HHmm]",
    "LATO - Piątek - 1": "SUMMER – Friday – slot 1",
    "LATO - Piątek - 1 [AATT]": "SUMMER – Friday – slot 1 [intensity/temp]",
    "LATO - Piątek - 2": "SUMMER – Friday – slot 2",
    "LATO - Piątek - 2 [AATT]": "SUMMER – Friday – slot 2 [intensity/temp]",
    "LATO - Piątek - 3": "SUMMER – Friday – slot 3",
    "LATO - Piątek - 3 [AATT]": "SUMMER – Friday – slot 3 [intensity/temp]",
    "LATO - Piątek - 4": "SUMMER – Friday – slot 4",
    "LATO - Piątek - 4 [AATT]": "SUMMER – Friday – slot 4 [intensity/temp]",
    "LATO - Piątek - Wietrzenie [GGMM]": "SUMMER – Friday – airing time [HHmm]",
    "LATO - Sobota - 1": "SUMMER – Saturday – slot 1",
    "LATO - Sobota - 1 [AATT]": "SUMMER – Saturday – slot 1 [intensity/temp]",
    "LATO - Sobota - 2": "SUMMER – Saturday – slot 2",
    "LATO - Sobota - 2 [AATT]": "SUMMER – Saturday – slot 2 [intensity/temp]",
    "LATO - Sobota - 3": "SUMMER – Saturday – slot 3",
    "LATO - Sobota - 3 [AATT]": "SUMMER – Saturday – slot 3 [intensity/temp]",
    "LATO - Sobota - 4": "SUMMER – Saturday – slot 4",
    "LATO - Sobota - 4 [AATT]": "SUMMER – Saturday – slot 4 [intensity/temp]",
    "LATO - Sobota - Wietrzenie [GGMM]": "SUMMER – Saturday – airing time [HHmm]",
    "LATO - Niedziela - 1": "SUMMER – Sunday – slot 1",
    "LATO - Niedziela - 1 [AATT]": "SUMMER – Sunday – slot 1 [intensity/temp]",
    "LATO - Niedziela - 2": "SUMMER – Sunday – slot 2",
    "LATO - Niedziela - 2 [AATT]": "SUMMER – Sunday – slot 2 [intensity/temp]",
    "LATO - Niedziela - 3": "SUMMER – Sunday – slot 3",
    "LATO - Niedziela - 3 [AATT]": "SUMMER – Sunday – slot 3 [intensity/temp]",
    "LATO - Niedziela - 4": "SUMMER – Sunday – slot 4",
    "LATO - Niedziela - 4 [AATT]": "SUMMER – Sunday – slot 4 [intensity/temp]",
    "LATO - Niedziela - Wietrzenie [GGMM]": "SUMMER – Sunday – airing time [HHmm]",

    # ---- Schedule – WINTER (ZIMA) ----
    "ZIMA - Poniedziałek - 1": "WINTER – Monday – slot 1",
    "ZIMA - Poniedziałek - 1 [AATT]": "WINTER – Monday – slot 1 [intensity/temp]",
    "ZIMA - Poniedziałek - 2": "WINTER – Monday – slot 2",
    "ZIMA - Poniedziałek - 2 [AATT]": "WINTER – Monday – slot 2 [intensity/temp]",
    "ZIMA - Poniedziałek - 3": "WINTER – Monday – slot 3",
    "ZIMA - Poniedziałek - 3 [AATT]": "WINTER – Monday – slot 3 [intensity/temp]",
    "ZIMA - Poniedziałek - 4": "WINTER – Monday – slot 4",
    "ZIMA - Poniedziałek - 4 [AATT]": "WINTER – Monday – slot 4 [intensity/temp]",
    "ZIMA - Poniedziałek - Wietrzenie [GGMM]": "WINTER – Monday – airing time [HHmm]",
    "ZIMA - Wtorek - 1": "WINTER – Tuesday – slot 1",
    "ZIMA - Wtorek - 1 [AATT]": "WINTER – Tuesday – slot 1 [intensity/temp]",
    "ZIMA - Wtorek - 2": "WINTER – Tuesday – slot 2",
    "ZIMA - Wtorek - 2 [AATT]": "WINTER – Tuesday – slot 2 [intensity/temp]",
    "ZIMA - Wtorek - 3": "WINTER – Tuesday – slot 3",
    "ZIMA - Wtorek - 3 [AATT]": "WINTER – Tuesday – slot 3 [intensity/temp]",
    "ZIMA - Wtorek - 4": "WINTER – Tuesday – slot 4",
    "ZIMA - Wtorek - 4 [AATT]": "WINTER – Tuesday – slot 4 [intensity/temp]",
    "ZIMA - Wtorek - Wietrzenie [GGMM]": "WINTER – Tuesday – airing time [HHmm]",
    "ZIMA - Środa - 1": "WINTER – Wednesday – slot 1",
    "ZIMA - Środa - 1 [AATT]": "WINTER – Wednesday – slot 1 [intensity/temp]",
    "ZIMA - Środa - 2": "WINTER – Wednesday – slot 2",
    "ZIMA - Środa - 2 [AATT]": "WINTER – Wednesday – slot 2 [intensity/temp]",
    "ZIMA - Środa - 3": "WINTER – Wednesday – slot 3",
    "ZIMA - Środa - 3 [AATT]": "WINTER – Wednesday – slot 3 [intensity/temp]",
    "ZIMA - Środa - 4": "WINTER – Wednesday – slot 4",
    "ZIMA - Środa - 4 [AATT]": "WINTER – Wednesday – slot 4 [intensity/temp]",
    "ZIMA - Środa - Wietrzenie [GGMM]": "WINTER – Wednesday – airing time [HHmm]",
    "ZIMA - Czwartek - 1": "WINTER – Thursday – slot 1",
    "ZIMA - Czwartek - 1 [AATT]": "WINTER – Thursday – slot 1 [intensity/temp]",
    "ZIMA - Czwartek - 2": "WINTER – Thursday – slot 2",
    "ZIMA - Czwartek - 2 [AATT]": "WINTER – Thursday – slot 2 [intensity/temp]",
    "ZIMA - Czwartek - 3": "WINTER – Thursday – slot 3",
    "ZIMA - Czwartek - 3 [AATT]": "WINTER – Thursday – slot 3 [intensity/temp]",
    "ZIMA - Czwartek - 4": "WINTER – Thursday – slot 4",
    "ZIMA - Czwartek - 4 [AATT]": "WINTER – Thursday – slot 4 [intensity/temp]",
    "ZIMA - Czwartek - Wietrzenie [GGMM]": "WINTER – Thursday – airing time [HHmm]",
    "ZIMA - Piątek - 1": "WINTER – Friday – slot 1",
    "ZIMA - Piątek - 1 [AATT]": "WINTER – Friday – slot 1 [intensity/temp]",
    "ZIMA - Piątek - 2": "WINTER – Friday – slot 2",
    "ZIMA - Piątek - 2 [AATT]": "WINTER – Friday – slot 2 [intensity/temp]",
    "ZIMA - Piątek - 3": "WINTER – Friday – slot 3",
    "ZIMA - Piątek - 3 [AATT]": "WINTER – Friday – slot 3 [intensity/temp]",
    "ZIMA - Piątek - 4": "WINTER – Friday – slot 4",
    "ZIMA - Piątek - 4 [AATT]": "WINTER – Friday – slot 4 [intensity/temp]",
    "ZIMA - Piątek - Wietrzenie [GGMM]": "WINTER – Friday – airing time [HHmm]",
    "ZIMA - Sobota - 1": "WINTER – Saturday – slot 1",
    "ZIMA - Sobota - 1 [AATT]": "WINTER – Saturday – slot 1 [intensity/temp]",
    "ZIMA - Sobota - 2": "WINTER – Saturday – slot 2",
    "ZIMA - Sobota - 2 [AATT]": "WINTER – Saturday – slot 2 [intensity/temp]",
    "ZIMA - Sobota - 3": "WINTER – Saturday – slot 3",
    "ZIMA - Sobota - 3 [AATT]": "WINTER – Saturday – slot 3 [intensity/temp]",
    "ZIMA - Sobota - 4": "WINTER – Saturday – slot 4",
    "ZIMA - Sobota - 4 [AATT]": "WINTER – Saturday – slot 4 [intensity/temp]",
    "ZIMA - Sobota - Wietrzenie [GGMM]": "WINTER – Saturday – airing time [HHmm]",
    "ZIMA - Niedziela - 1": "WINTER – Sunday – slot 1",
    "ZIMA - Niedziela - 1 [AATT]": "WINTER – Sunday – slot 1 [intensity/temp]",
    "ZIMA - Niedziela - 2": "WINTER – Sunday – slot 2",
    "ZIMA - Niedziela - 2 [AATT]": "WINTER – Sunday – slot 2 [intensity/temp]",
    "ZIMA - Niedziela - 3": "WINTER – Sunday – slot 3",
    "ZIMA - Niedziela - 3 [AATT]": "WINTER – Sunday – slot 3 [intensity/temp]",
    "ZIMA - Niedziela - 4": "WINTER – Sunday – slot 4",
    "ZIMA - Niedziela - 4 [AATT]": "WINTER – Sunday – slot 4 [intensity/temp]",
    "ZIMA - Niedziela - Wietrzenie [GGMM]": "WINTER – Sunday – airing time [HHmm]",
}


def translate(polish: str) -> str | None:
    """Return English translation or None if not found."""
    return FULL_TRANSLATIONS.get(polish)


def main() -> int:
    data = json.loads(REGISTER_FILE.read_text(encoding="utf-8"))
    registers: list[dict] = data.get("registers", [])

    translated = 0
    todo = 0
    already_ok = 0

    for reg in registers:
        desc_pl = reg.get("description", "")
        desc_en = reg.get("description_en", "")

        if desc_en and desc_en != desc_pl:
            already_ok += 1
            continue  # already has a different (presumably English) translation

        if not desc_pl:
            continue

        en = translate(desc_pl)
        if en is not None:
            reg["description_en"] = en
            translated += 1
        else:
            reg["description_en"] = f"[TODO] {desc_pl}"
            todo += 1

    REGISTER_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Translated:   {translated}")
    print(f"Already OK:   {already_ok}")
    print(f"TODO (unmatched): {todo}")
    if todo:
        print("\nUnmatched descriptions (need manual translation):")
        for reg in registers:
            if reg.get("description_en", "").startswith("[TODO]"):
                print(f"  [{reg['function']} addr={reg['address_dec']}] {reg['name']}: {reg['description']}")
    return 0 if todo == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
