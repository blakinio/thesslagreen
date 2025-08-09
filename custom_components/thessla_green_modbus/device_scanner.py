"""Enhanced device scanner for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
Autoscan rejestrów + diagnostyka + logowanie błędów
"""
from __future__ import annotations

from typing import Dict, List, Any, Optional

class DeviceCapabilities:
    """Represents detected device capabilities."""
    
    def __init__(
        self,
        has_temperature_sensors: bool = False,
        has_flow_sensors: bool = False,
        has_gwc: bool = False,
        has_bypass: bool = False,
        has_heating: bool = False,
        has_scheduling: bool = False,
        has_air_quality: bool = False,
        has_pressure_sensors: bool = False,
        has_filter_monitoring: bool = False,
        has_constant_flow: bool = False,
        special_functions: Optional[List[str]] = None,
        operating_modes: Optional[List[str]] = None,
    ):
        """Initialize device capabilities."""
        self.has_temperature_sensors = has_temperature_sensors
        self.has_flow_sensors = has_flow_sensors
        self.has_gwc = has_gwc
        self.has_bypass = has_bypass
        self.has_heating = has_heating
        self.has_scheduling = has_scheduling
        self.has_air_quality = has_air_quality
        self.has_pressure_sensors = has_pressure_sensors
        self.has_filter_monitoring = has_filter_monitoring
        self.has_constant_flow = has_constant_flow
        self.special_functions = special_functions or []
        self.operating_modes = operating_modes or []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "has_temperature_sensors": self.has_temperature_sensors,
            "has_flow_sensors": self.has_flow_sensors,
            "has_gwc": self.has_gwc,
            "has_bypass": self.has_bypass,
            "has_heating": self.has_heating,
            "has_scheduling": self.has_scheduling,
            "has_air_quality": self.has_air_quality,
            "has_pressure_sensors": self.has_pressure_sensors,
            "has_filter_monitoring": self.has_filter_monitoring,
            "has_constant_flow": self.has_constant_flow,
            "special_functions": self.special_functions,
            "operating_modes": self.operating_modes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceCapabilities':
        """Create instance from dictionary."""
        return cls(
            has_temperature_sensors=data.get("has_temperature_sensors", False),
            has_flow_sensors=data.get("has_flow_sensors", False),
            has_gwc=data.get("has_gwc", False),
            has_bypass=data.get("has_bypass", False),
            has_heating=data.get("has_heating", False),
            has_scheduling=data.get("has_scheduling", False),
            has_air_quality=data.get("has_air_quality", False),
            has_pressure_sensors=data.get("has_pressure_sensors", False),
            has_filter_monitoring=data.get("has_filter_monitoring", False),
            has_constant_flow=data.get("has_constant_flow", False),
            special_functions=data.get("special_functions", []),
            operating_modes=data.get("operating_modes", []),
        )