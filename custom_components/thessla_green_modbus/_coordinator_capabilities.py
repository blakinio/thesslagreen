"""Capabilities and derived metrics mixin for coordinator."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, ClassVar

_LOGGER = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class _CoordinatorCapabilitiesMixin:
    """Capability and derived-value logic for the coordinator."""

    device_info: dict[str, Any]
    _last_power_timestamp: datetime | None
    _total_energy: float

    _STANDBY_POWER_W: float = 10.0
    _MODEL_POWER_DATA: ClassVar[Mapping[int, tuple[float, float]]] = MappingProxyType(
        {
            300: (105.0, 1150.0),
            400: (170.0, 1500.0),
            420: (94.0, 1449.0),
            500: (255.0, 1850.0),
            550: (345.0, 1950.0),
        }
    )
    _MODEL_FLOW_TOLERANCE = 15

    def _lookup_model_power(self, nominal_flow: float) -> tuple[float, float] | None:
        """Return (fan_total_max_W, heater_max_W) for the closest known model.

        Returns ``None`` when no entry is within ``_MODEL_FLOW_TOLERANCE`` m³/h.
        """
        best: tuple[int, tuple[float, float]] | None = None
        for flow_key, specs in self._MODEL_POWER_DATA.items():
            diff = abs(nominal_flow - flow_key)
            if diff <= self._MODEL_FLOW_TOLERANCE:
                if best is None or diff < abs(nominal_flow - best[0]):
                    best = (flow_key, specs)
        return best[1] if best is not None else None

    def calculate_power_consumption(self, data: dict[str, Any]) -> float | None:
        """Calculate electrical power consumption.

        When the device's nominal airflow is recognised the calculation uses
        the fan affinity law applied to the *measured* supply and exhaust flow
        rates together with model-specific max-power values taken from the
        official datasheet / nameplate.  This gives ±10-15 % accuracy.

        For an unknown model the method falls back to a cubic estimate based
        on the DAC output voltages (previous behaviour, ±40-50 % accuracy).
        """
        nominal_raw = data.get("nominal_supply_air_flow")
        supply_flow = data.get("supply_flow_rate")
        exhaust_flow = data.get("exhaust_flow_rate")

        if nominal_raw is not None and supply_flow is not None and exhaust_flow is not None:
            try:
                nominal = float(nominal_raw)
                q_s = max(0.0, float(supply_flow))
                q_e = max(0.0, float(exhaust_flow))
                specs = self._lookup_model_power(nominal)
                if specs is not None and nominal > 0:
                    fan_total_max, heater_max = specs
                    # Fan affinity law: P ∝ Q³, split equally between both fans.
                    fan_per = fan_total_max / 2.0
                    p_fans = fan_per * (q_s / nominal) ** 3 + fan_per * (q_e / nominal) ** 3

                    # Heater: PWM-controlled resistive element → linear with DAC voltage.
                    dac_h = float(data.get("dac_heater", 0) or 0)
                    dac_h = max(0.0, min(10.0, dac_h))
                    p_heater = heater_max * (dac_h / 10.0)

                    return round(p_fans + p_heater + self._STANDBY_POWER_W, 1)
            except (TypeError, ValueError) as exc:
                _LOGGER.debug("Power calculation via flow/DAC unavailable: %s", exc)

        # Fallback: DAC-voltage cubic estimate (model unknown or flow unavailable).
        try:
            v_s = float(data["dac_supply"])
            v_e = float(data["dac_exhaust"])
        except (KeyError, TypeError, ValueError):
            return None

        def _dac_power(v: float, p_max: float) -> float:
            v = max(0.0, min(10.0, v))
            return (v / 10) ** 3 * p_max

        power = _dac_power(v_s, 80.0) + _dac_power(v_e, 80.0)
        dac_h = float(data.get("dac_heater", 0) or 0)
        if dac_h:
            power += _dac_power(dac_h, 2000.0)
        dac_c = float(data.get("dac_cooler", 0) or 0)
        if dac_c:
            power += _dac_power(dac_c, 1000.0)
        return round(power, 1)

    def _post_process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Post-process data to calculate derived values."""
        # Expose the full serial number (assembled from 6 registers by the scanner)
        # as a sensor value so the serial_number entity has a meaningful state.
        device_serial = (self.device_info or {}).get("serial_number")
        if device_serial and device_serial != "Unknown":
            data["serial_number"] = device_serial

        # Calculate heat recovery efficiency.
        # bypass_mode register 4330: 0=inactive (HX active), 1=freeheating, 2=freecooling.
        # Both freeheating and freecooling open the bypass damper, routing air
        # around the heat exchanger, so any temperature-based efficiency formula
        # yields a meaningless result — skip for both active states.
        #
        # Formula selection (per EN 308 / ASHRAE Standard 84):
        #   • With flow rates: thermodynamic effectiveness ε (ASHRAE 84 ε-NTU):
        #       ε = Q_supply × (T_supply − T_outside) / (Q_min × (T_exhaust − T_outside))
        #     where Q_min = min(Q_supply, Q_exhaust).
        #     Correctly bounded [0, 1] even for unbalanced flows.
        #   • Without flow rates: EN 308 supply-side temperature efficiency η_supply
        #     (3-sensor formula, valid when flows are approximately balanced):
        #       η = (T_supply − T_outside) / (T_exhaust − T_outside)
        #     Note: this device exposes only 3 temperature sensors (TZ1, TN1, TP);
        #     the exhaust-outlet sensor TW is absent, so EN 308 η_exhaust and the
        #     Belgian mean-efficiency (η_epbd) cannot be computed.
        bypass_raw = data.get("bypass_mode")
        bypass_open = bypass_raw in (1, 2)
        if (
            all(
                k in data
                for k in ["outside_temperature", "supply_temperature", "exhaust_temperature"]
            )
            and not bypass_open
        ):
            try:
                outside = float(data["outside_temperature"])
                supply = float(data["supply_temperature"])
                exhaust = float(data["exhaust_temperature"])

                # Heat recovery only makes sense in heating mode:
                # outside must be colder than the room (exhaust > outside).
                # In summer/freecooling the bypass should be open, but if the
                # bypass register hasn't caught up yet, skip gracefully.
                # EN 308 also requires ΔT ≥ 5 K for a statistically reliable
                # measurement; below that threshold sensor noise dominates.
                _MIN_DELTA_T = 5.0
                if exhaust - outside >= _MIN_DELTA_T:
                    q_supply = data.get("supply_flow_rate")
                    q_exhaust = data.get("exhaust_flow_rate")
                    if q_supply is not None and q_exhaust is not None:
                        q_s = float(q_supply)
                        q_e = float(q_exhaust)
                        q_min = min(q_s, q_e)
                        if q_min > 0:
                            # ASHRAE 84 thermodynamic effectiveness (ε-NTU)
                            raw = (q_s * (supply - outside)) / (q_min * (exhaust - outside))
                        else:
                            raw = (supply - outside) / (exhaust - outside)
                    else:
                        # EN 308 η_supply — 3-sensor fallback
                        raw = (supply - outside) / (exhaust - outside)

                    efficiency = round(raw * 100, 1)
                    data["calculated_efficiency"] = max(0.0, min(100.0, efficiency))
                    data["heat_recovery_efficiency"] = data["calculated_efficiency"]
            except (ZeroDivisionError, TypeError, ValueError) as exc:
                _LOGGER.debug("Could not calculate efficiency: %s", exc)

        # Calculate heat recovery power: P[W] = ρ·Cp·Q·ΔT
        # ρ=1.2 kg/m³, Cp=1005 J/(kg·K) → coefficient = 1.2*1005/3600 ≈ 0.335 W/(m³/h·K)
        if all(
            k in data for k in ["supply_flow_rate", "outside_temperature", "supply_temperature"]
        ):
            try:
                flow = float(data["supply_flow_rate"])
                delta_t = float(data["supply_temperature"]) - float(data["outside_temperature"])
                data["heat_recovery_power"] = round(max(0.0, 0.335 * flow * delta_t), 1)
            except (TypeError, ValueError) as exc:
                _LOGGER.debug("Could not calculate heat recovery power: %s", exc)

        # Calculate flow balance
        if "supply_flow_rate" in data and "exhaust_flow_rate" in data:
            try:
                balance = float(data["supply_flow_rate"]) - float(data["exhaust_flow_rate"])
                data["flow_balance"] = balance
                data["flow_balance_status"] = (
                    "balanced"
                    if abs(balance) < 10
                    else "supply_dominant"
                    if balance > 0
                    else "exhaust_dominant"
                )
            except (TypeError, ValueError) as exc:
                _LOGGER.debug("Could not calculate flow balance: %s", exc)
        power = self.calculate_power_consumption(data)
        if power is not None:
            data["estimated_power"] = power
            data["electrical_power"] = power
            now = _utcnow()
            last_ts = self._last_power_timestamp
            if not isinstance(last_ts, datetime):
                elapsed = 0.0
            else:
                if (
                    getattr(now, "tzinfo", None) is not None
                    and getattr(last_ts, "tzinfo", None) is None
                ):
                    last_ts = last_ts.replace(tzinfo=UTC)
                elif (
                    getattr(now, "tzinfo", None) is None
                    and getattr(last_ts, "tzinfo", None) is not None
                ):
                    now = now.replace(tzinfo=UTC)
                elapsed = (now - last_ts).total_seconds()
            self._total_energy += power * elapsed / 3600000.0
            data["total_energy"] = self._total_energy
            self._last_power_timestamp = now

        # Decode device clock from BCD registers 0-3
        try:
            raw_yymm = data.get("date_time")
            raw_ddtt = data.get("date_time_ddtt")
            raw_ggmm = data.get("date_time_ggmm")
            raw_sscc = data.get("date_time_sscc")
            if (
                raw_yymm is not None
                and raw_ddtt is not None
                and raw_ggmm is not None
                and raw_sscc is not None
            ):

                def _bcd(b: int) -> int:
                    return ((b >> 4) & 0xF) * 10 + (b & 0xF)

                yy = _bcd((raw_yymm >> 8) & 0xFF)
                mm = _bcd(raw_yymm & 0xFF)
                dd = _bcd((raw_ddtt >> 8) & 0xFF)
                hh = _bcd((raw_ggmm >> 8) & 0xFF)
                mi = _bcd(raw_ggmm & 0xFF)
                ss = _bcd((raw_sscc >> 8) & 0xFF)
                year = 2000 + yy
                if 1 <= mm <= 12 and 1 <= dd <= 31 and hh <= 23 and mi <= 59 and ss <= 59:
                    data["device_clock"] = (
                        f"{year:04d}-{mm:02d}-{dd:02d}T{hh:02d}:{mi:02d}:{ss:02d}"
                    )
        except (TypeError, ValueError, AttributeError) as exc:
            _LOGGER.debug("Failed to decode device clock: %s", exc)

        return data
