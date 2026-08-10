from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace(path: str, old: str, new: str, *, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} matches, found {actual}: {old!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


flow_path = "custom_components/thessla_green_modbus/_config_flow/__init__.py"

replace(
    flow_path,
    "from .entry import build_unique_id as _build_unique_id_impl\n"
    "from .entry import prepare_entry_payload as _prepare_entry_payload_impl\n",
    "from .entry import build_connection_match as _build_connection_match_impl\n"
    "from .entry import build_stable_unique_id as _build_stable_unique_id_impl\n"
    "from .entry import prepare_entry_payload as _prepare_entry_payload_impl\n",
)

old_reconfigure = '''    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow user to update host/port/slave_id without removing the entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema_impl(entry.data),
        )
'''
new_reconfigure = '''    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and update host/port/slave_id without recreating the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            candidate = dict(entry.data)
            candidate.update(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                }
            )
            info, submit_errors = await _process_user_submission_impl(
                candidate,
                validate_input=validate_input,
                hass=self.hass,
                logger=_LOGGER,
            )
            if info is not None:
                self._device_info, self._scan_result = _extract_discovered_state_impl(info)
                stable_unique_id = self._build_stable_unique_id(self._device_info)
                updated_unique_id = entry.unique_id
                if stable_unique_id and stable_unique_id != entry.unique_id:
                    await self.async_set_unique_id(stable_unique_id)
                    self._abort_if_unique_id_configured()
                    updated_unique_id = stable_unique_id
                return self.async_update_and_abort(
                    entry,
                    unique_id=updated_unique_id,
                    data_updates={
                        CONF_HOST: candidate[CONF_HOST],
                        CONF_PORT: candidate[CONF_PORT],
                        CONF_SLAVE_ID: candidate[CONF_SLAVE_ID],
                    },
                )
            errors.update(submit_errors)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema_impl(entry.data),
            errors=errors,
        )
'''
replace(flow_path, old_reconfigure, new_reconfigure)

replace(
    flow_path,
    '''    @staticmethod
    def _build_unique_id(data: dict[str, Any]) -> str:
        """Generate a unique identifier for the config entry."""
        return _build_unique_id_impl(data)
''',
    '''    @staticmethod
    def _build_stable_unique_id(device_info: dict[str, Any]) -> str | None:
        """Return a stable device-derived config-entry unique ID when available."""
        return _build_stable_unique_id_impl(device_info)

    @staticmethod
    def _build_connection_match(data: dict[str, Any]) -> dict[str, Any]:
        """Return connection fields used only for duplicate-entry matching."""
        return _build_connection_match_impl(data)

    async def _async_apply_validated_identity(self, data: dict[str, Any]) -> None:
        """Apply stable device identity or fall back to connection duplicate matching."""
        stable_unique_id = self._build_stable_unique_id(self._device_info)
        if stable_unique_id:
            await self.async_set_unique_id(stable_unique_id)
            self._abort_if_unique_id_configured()
            return
        self._async_abort_entries_match(self._build_connection_match(data))
''',
)

replace(
    flow_path,
    '''        if user_input is not None:
            await self.async_set_unique_id(self._build_unique_id(self._data))
            self._abort_if_unique_id_configured()
            entry_data, options = self._prepare_entry_payload(cap_cls)
''',
    '''        if user_input is not None:
            entry_data, options = self._prepare_entry_payload(cap_cls)
''',
)

replace(
    flow_path,
    '''    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery of AirPack device."""
        await self.async_set_unique_id(discovery_info.host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
        self._discovered_host = discovery_info.host
        return await self.async_step_user()
''',
    '''    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery without treating a hostname as stable identity."""
        self._async_abort_entries_match({CONF_HOST: discovery_info.host})
        self._discovered_host = discovery_info.host
        return await self.async_step_user()
''',
)

replace(
    flow_path,
    '''                await self.async_set_unique_id(self._build_unique_id(user_input))
                self._abort_if_unique_id_configured()
                return await self.async_step_confirm()
''',
    '''                await self._async_apply_validated_identity(user_input)
                return await self.async_step_confirm()
''',
)

# Pure helper tests prove IP/serial-path are duplicate-match data, never persistent unique IDs.
test_path = ROOT / "tests/test_config_flow_stable_identity.py"
test_path.write_text(
    '''"""Stable config-entry identity and connection-match regression tests."""\n\nfrom custom_components.thessla_green_modbus._config_flow.entry import (\n    build_connection_match,\n    build_stable_unique_id,\n)\nfrom custom_components.thessla_green_modbus.const import (\n    CONF_CONNECTION_TYPE,\n    CONF_SERIAL_PORT,\n    CONF_SLAVE_ID,\n    CONNECTION_TYPE_RTU,\n    CONNECTION_TYPE_TCP,\n)\nfrom homeassistant.const import CONF_HOST, CONF_PORT\n\n\ndef test_stable_unique_id_uses_confirmed_serial() -> None:\n    assert build_stable_unique_id({"serial_number": " AP4-00123 "}) == "serial:ap4-00123"\n\n\ndef test_stable_unique_id_rejects_placeholder_identity() -> None:\n    for value in (None, "", "Unknown", "N/A", "0"):\n        assert build_stable_unique_id({"serial_number": value}) is None\n\n\ndef test_tcp_connection_identity_is_match_data_not_unique_id() -> None:\n    data = {\n        CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,\n        CONF_HOST: "airpack.local",\n        CONF_PORT: 8899,\n        CONF_SLAVE_ID: 10,\n    }\n    assert build_connection_match(data) == data\n    assert build_stable_unique_id(data) is None\n\n\ndef test_rtu_connection_identity_is_match_data_not_unique_id() -> None:\n    data = {\n        CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,\n        CONF_SERIAL_PORT: "/dev/serial/by-id/airpack",\n        CONF_SLAVE_ID: 10,\n    }\n    assert build_connection_match(data) == data\n    assert build_stable_unique_id(data) is None\n''',
    encoding="utf-8",
)

# Replace obsolete duplicate-flow tests with the new validated-identity contract.
dup_path = ROOT / "tests/test_config_flow_user_duplicates.py"
dup_path.write_text(
    '''"""Duplicate-handling user-flow tests for stable config-entry identity."""\n\nfrom types import SimpleNamespace\nfrom unittest.mock import AsyncMock, MagicMock, patch\n\nimport pytest\nfrom custom_components.thessla_green_modbus.config_flow import ConfigFlow\nfrom custom_components.thessla_green_modbus.const import (\n    CONF_CONNECTION_TYPE,\n    CONF_SLAVE_ID,\n    CONNECTION_TYPE_TCP,\n)\nfrom homeassistant.const import CONF_HOST, CONF_PORT\n\nCONF_NAME = "name"\nDEFAULT_USER_INPUT = {\n    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,\n    CONF_HOST: "192.168.1.100",\n    CONF_PORT: 502,\n    CONF_SLAVE_ID: 10,\n    CONF_NAME: "My Device",\n}\n\n\nclass AbortFlow(Exception):\n    def __init__(self, reason: str) -> None:\n        super().__init__(reason)\n        self.reason = reason\n\n\n@pytest.mark.asyncio\nasync def test_duplicate_serial_aborts_during_validated_user_step() -> None:\n    flow = ConfigFlow()\n    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))\n    validation_result = {\n        "title": "ThesslaGreen",\n        "device_info": {"serial_number": "AP4-00123"},\n        "scan_result": {},\n    }\n    with (\n        patch(\n            "custom_components.thessla_green_modbus._config_flow.validate_input",\n            return_value=validation_result,\n        ),\n        patch.object(flow, "async_set_unique_id", new=AsyncMock()),\n        patch.object(\n            flow,\n            "_abort_if_unique_id_configured",\n            side_effect=AbortFlow("already_configured"),\n        ),\n        pytest.raises(AbortFlow) as err,\n    ):\n        await flow.async_step_user(DEFAULT_USER_INPUT)\n    assert err.value.reason == "already_configured"\n    flow.async_set_unique_id.assert_awaited_once_with("serial:ap4-00123")\n\n\n@pytest.mark.asyncio\nasync def test_missing_serial_uses_connection_duplicate_match() -> None:\n    flow = ConfigFlow()\n    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))\n    validation_result = {"title": "ThesslaGreen", "device_info": {}, "scan_result": {}}\n    with (\n        patch(\n            "custom_components.thessla_green_modbus._config_flow.validate_input",\n            return_value=validation_result,\n        ),\n        patch.object(flow, "_async_abort_entries_match") as abort_match,\n        patch.object(flow, "async_step_confirm", new=AsyncMock(return_value={"type": "form"})),\n    ):\n        await flow.async_step_user(DEFAULT_USER_INPUT)\n    abort_match.assert_called_once_with(\n        {\n            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,\n            CONF_HOST: "192.168.1.100",\n            CONF_PORT: 502,\n            CONF_SLAVE_ID: 10,\n        }\n    )\n''',
    encoding="utf-8",
)

Path(__file__).unlink()
