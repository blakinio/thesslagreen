"""Bounded user-level filter alarm acknowledgement for AirPack Home.

Vendor MODBUS_USER_AirPack_Home_06.2021.01, pages 16-17:
S17 FC03/8209 and E252 FC03/8444 are R/W; 0 means absent.
Hardware-verified on Home firmware 3.11: writing 1 acknowledges an ACTIVE alarm.
The written acknowledgement value differs from the resulting readback state.
This never changes filter type, pressure protection or factory settings.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ..device_profile import configured_device_family
from .handler_deps import ServiceHandlerDeps
from .schema import _target_schema

FILTER_ALARMS = {"S17": ("s_17", 8209), "E252": ("e_252", 8444)}
DIAGNOSTIC_REGISTERS = {
    "access_level": 15,
    "filter_change": 8191,
    "s_17": 8209,
    "e_252": 8444,
    "stop_ahu_code": 4384,
    "on_off_panel_mode": 4387,
    "mode": 4208,
    "air_flow_rate_manual": 4210,
    "air_flow_rate_temporary": 4211,
    "cfg_mode_1": 4400,
    "air_flow_rate_temporary_4401": 4401,
    "airflow_rate_change_flag": 4402,
}
RESET_FILTER_ALARMS_SCHEMA = _target_schema(
    {
        vol.Required("device_family"): vol.In(("airpack_home",)),
        vol.Required("confirm_filters_replaced"): vol.In((True,)),
        vol.Required("codes"): vol.All([vol.In(tuple(FILTER_ALARMS))], vol.Length(min=1, max=2)),
        vol.Optional("write_method", default="single"): vol.In(("single", "multiple")),
    }
)


async def acknowledge_filter_alarms(
    coordinator: Any, codes: list[str], write_method: str = "single"
) -> dict[str, int]:
    """Read, acknowledge once and verify under the existing transport lock."""
    if configured_device_family(coordinator) not in ("unspecified", "airpack_home"):
        raise ServiceValidationError("This alarm reset is documented only for AirPack Home")
    if not codes or any(code not in FILTER_ALARMS for code in codes):
        raise ServiceValidationError("Only S17 and E252 filter alarms may be acknowledged")
    if write_method not in ("single", "multiple"):
        raise ServiceValidationError("Unsupported Modbus write function")
    observed: dict[str, int] = {}
    device_info = getattr(coordinator._device_client, "device_info", None) or {}
    firmware = str(device_info.get("firmware", ""))
    firmware_parts = firmware.strip().lstrip("vV").split(".")
    # Verified on the owner's 3.11 controller: write 1, then require state 0.
    # Preserve existing behavior for other firmware; never write an inactive flag.
    acknowledge_value = 1 if firmware_parts[:2] == ["3", "11"] else 0
    async with coordinator._device_client._write_lock:
        await coordinator._ensure_connection()
        # Preserve the user's selected system; acknowledge only known filter alarms.
        # Home register 8191: 1=presostat, 2=flat filters (timed replacement).
        # Neither this acknowledgement nor its validation changes register 8191.
        if await coordinator._locked_read_holding_registers(8191, count=1) not in ([1], [2]):
            raise ServiceValidationError("A fresh read must confirm Home filter type 1 or 2")
        for code in dict.fromkeys(codes):
            name, address = FILTER_ALARMS[code]
            before = await coordinator._locked_read_holding_registers(address, count=1)
            if before not in ([0], [1]):
                raise HomeAssistantError(f"Cannot read {code}; no acknowledgement sent for it")
            if before == [1]:
                if write_method == "multiple":
                    _, ok = await coordinator._write_holding_multi(address, [acknowledge_value], 1)
                else:
                    ok, _ = await coordinator._locked_single_register_write(
                        register_name=name, value=acknowledge_value, offset=0, refresh=False
                    )
                if not ok:
                    raise HomeAssistantError(f"Device did not confirm acknowledgement of {code}")
            after = await coordinator._locked_read_holding_registers(address, count=1)
            if after != [0]:
                raise HomeAssistantError(
                    f"{code} reset not verified: before={before!r}, after={after!r}"
                )
            observed[name] = 0
    await coordinator.async_request_refresh()
    return observed


def register_filter_alarm_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register explicit, manual acknowledgement; never retry automatically."""

    async def reset_filter_alarms(call: ServiceCall) -> None:
        if (
            call.data.get("confirm_filters_replaced") is not True
            or call.data.get("device_family") != "airpack_home"
        ):
            raise ServiceValidationError("Confirm AirPack Home and physical filter replacement")
        targets = await deps.iter_target_coordinators(hass, call)
        # An explicit action must address one physical unit only.
        unique = {id(coordinator): coordinator for _, coordinator in targets}
        if len(unique) != 1:
            raise ServiceValidationError("Select exactly one AirPack Home device")
        await acknowledge_filter_alarms(
            next(iter(unique.values())),
            call.data.get("codes", []),
            call.data.get("write_method", "single"),
        )

    hass.services.async_register(
        deps.domain,
        "reset_filter_alarms",
        reset_filter_alarms,
        RESET_FILTER_ALARMS_SCHEMA,
    )

    async def filter_alarm_diagnostics(call: ServiceCall) -> dict[str, Any]:
        targets = await deps.iter_target_coordinators(hass, call)
        unique = {id(coordinator): coordinator for _, coordinator in targets}
        if len(unique) != 1:
            raise ServiceValidationError("Select exactly one device for diagnostic reads")
        coordinator = next(iter(unique.values()))
        result: dict[str, int | None] = {}
        async with coordinator._device_client._write_lock:
            await coordinator._ensure_connection()
            for name, address in DIAGNOSTIC_REGISTERS.items():
                raw = await coordinator._locked_read_holding_registers(address, count=1)
                result[name] = raw[0] if raw is not None and len(raw) == 1 else None
        return {"registers": result, "writes_sent": 0}

    hass.services.async_register(
        deps.domain,
        "filter_alarm_diagnostics",
        filter_alarm_diagnostics,
        _target_schema(),
        supports_response=SupportsResponse.ONLY,
    )
