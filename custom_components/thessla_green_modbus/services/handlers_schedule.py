"""Schedule-related service registration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .handler_deps import ServiceHandlerDeps
from .schema import SET_AIRFLOW_SCHEDULE_SCHEMA


def _resolve_schedule_temperature_byte(
    coordinator: object, setting_register: str, temperature: float | None
) -> int:
    if temperature is not None:
        return max(0, min(39, round((temperature - 16.0) * 2)))

    current = coordinator.data.get(setting_register) if coordinator.data else None
    return int(current) & 0xFF if isinstance(current, int) else 0


def register_schedule_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register schedule-related services."""

    async def set_airflow_schedule(call: ServiceCall) -> None:
        day = deps.normalize_option(call.data["day"])
        period = int(deps.normalize_option(str(call.data["period"])))
        season = deps.normalize_option(call.data.get("season", "summer"))
        start_time = call.data["start_time"]
        end_time = call.data.get("end_time")
        airflow_rate = call.data["airflow_rate"]
        temperature = call.data.get("temperature")
        dow_key = deps.day_to_device_key[day]
        schedule_register = f"schedule_{season}_{dow_key}_{period}"
        setting_register = f"setting_{season}_{dow_key}_{period}"
        start_value = f"{start_time.hour:02d}:{start_time.minute:02d}"

        if end_time is not None:
            raise ServiceValidationError(
                "end_time cannot be written by AirPack4: a schedule slot ends "
                "when the next slot starts. Set the next slot's start_time instead."
            )

        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            holding = coordinator.device_client.available_registers.get("holding_registers", set())
            missing = {
                register
                for register in (schedule_register, setting_register)
                if register not in holding
            }
            if missing:
                raise ServiceValidationError(
                    f"{entity_id} does not expose required schedule registers: "
                    f"{', '.join(sorted(missing))}."
                )

            clamped_airflow = deps.clamp_airflow_rate(coordinator, airflow_rate)
            temp_byte = _resolve_schedule_temperature_byte(
                coordinator, setting_register, temperature
            )
            aatt_value = ((clamped_airflow & 0xFF) << 8) | (temp_byte & 0xFF)

            await deps.write_register(
                coordinator,
                schedule_register,
                start_value,
                entity_id,
                "set airflow schedule start",
            )
            await deps.write_register(
                coordinator,
                setting_register,
                aatt_value,
                entity_id,
                "set airflow schedule AATT",
            )

            await coordinator.async_request_refresh()
            deps.logger.info(
                "Set airflow schedule [%s %s slot %d] start=%s flow=%d%% on %s",
                season,
                dow_key,
                period,
                start_value,
                clamped_airflow,
                entity_id,
            )

    hass.services.async_register(
        deps.domain, "set_airflow_schedule", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_intensity", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
