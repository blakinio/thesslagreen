"""Safety-contract tests for advanced and destructive entities."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity
from homeassistant.helpers.entity import EntityCategory


class _TestEntity(ThesslaGreenEntity):
    """Minimal concrete entity for testing common risk policy."""


def _coordinator():
    client = SimpleNamespace(
        device_info={},
        config=SimpleNamespace(host="127.0.0.1", port=502),
        slave_id=10,
        offline_state=False,
    )
    return SimpleNamespace(
        device_client=client,
        get_device_info=lambda: {},
        last_update_success=True,
        data={},
    )


def test_risky_entity_is_disabled_by_default() -> None:
    entity = _TestEntity(_coordinator(), "dangerous", 1)
    entity._apply_risk_policy(
        {
            "risk_level": "advanced",
            "risk_category": "communication_lockout",
        }
    )

    assert entity._attr_entity_registry_enabled_default is False
    assert entity._attr_entity_category == EntityCategory.CONFIG


def test_normal_entity_default_is_not_overridden() -> None:
    entity = _TestEntity(_coordinator(), "normal", 2)
    entity._apply_risk_policy({})

    assert not hasattr(entity, "_attr_entity_registry_enabled_default")
