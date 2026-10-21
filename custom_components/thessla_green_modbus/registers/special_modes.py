"""Manufacturer FC03/4224 enum (Home 06.2021.01 and AirPack4 08.2022.01, p.11).

These values describe controller functions, not arbitrary HA lifestyle presets.
"""

SPECIAL_MODES: dict[str, int] = {
    "none": 0,
    "hood": 1,
    "fireplace": 2,
    "airing_doorbell": 3,
    "airing_switch": 4,
    "airing_hygrostat": 5,
    "airing_air_quality": 6,
    "airing_manual": 7,
    "airing_auto": 8,
    "airing_manual_timed": 9,
    "open_windows": 10,
    "empty_house": 11,
}
