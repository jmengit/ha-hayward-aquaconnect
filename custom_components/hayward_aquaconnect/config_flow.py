from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import AquaConnectClient, AquaConnectError
from .const import (
    CONF_BUTTON_DELAY,
    CONF_COMMAND_RETRIES,
    CONF_COMMAND_TIMEOUT,
    CONF_SLOT_OVERRIDES,
    DEFAULT_BUTTON_DELAY,
    DEFAULT_COMMAND_RETRIES,
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .slots import DEFAULT_EQUIPMENT_SLOTS


def _slot_overrides_to_text(overrides: Any) -> str:
    if not overrides:
        return ""
    return json.dumps(overrides, indent=2, sort_keys=True)


def _parse_slot_overrides(raw: str) -> dict[str, dict[str, Any]]:
    if not raw or not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("slot_overrides must be a JSON object")
    result: dict[str, dict[str, Any]] = {}
    known_slugs = {slot.slug for slot in DEFAULT_EQUIPMENT_SLOTS}
    for slug, value in parsed.items():
        if not isinstance(slug, str) or not isinstance(value, dict):
            raise ValueError("slot_overrides must map slot slugs to JSON objects")
        if slug not in known_slugs:
            raise ValueError(f"unknown slot slug: {slug}")
        result[slug] = value
    return result


class AquaConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                slot_overrides = _parse_slot_overrides(user_input[CONF_SLOT_OVERRIDES])
            except (json.JSONDecodeError, ValueError):
                errors[CONF_SLOT_OVERRIDES] = "invalid_json"
            else:
                host = user_input[CONF_HOST]
                session = async_create_clientsession(self.hass)
                client = AquaConnectClient(session, host)
                try:
                    await client.async_read_status()
                except AquaConnectError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Hayward AquaConnect",
                        data={
                            "host": host,
                            "scan_interval": user_input[CONF_SCAN_INTERVAL],
                        },
                        options={
                            CONF_COMMAND_TIMEOUT: user_input[CONF_COMMAND_TIMEOUT],
                            CONF_COMMAND_RETRIES: user_input[CONF_COMMAND_RETRIES],
                            CONF_BUTTON_DELAY: user_input[CONF_BUTTON_DELAY],
                            CONF_SLOT_OVERRIDES: slot_overrides,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.1.50"): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=3, max=60)),
                vol.Required(CONF_COMMAND_TIMEOUT, default=DEFAULT_COMMAND_TIMEOUT): vol.All(float, vol.Range(min=2, max=60)),
                vol.Required(CONF_COMMAND_RETRIES, default=DEFAULT_COMMAND_RETRIES): vol.All(int, vol.Range(min=0, max=3)),
                vol.Required(CONF_BUTTON_DELAY, default=DEFAULT_BUTTON_DELAY): vol.All(float, vol.Range(min=0.25, max=5)),
                vol.Required(CONF_SLOT_OVERRIDES, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return AquaConnectOptionsFlow(config_entry)


class AquaConnectOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                slot_overrides = _parse_slot_overrides(user_input[CONF_SLOT_OVERRIDES])
            except (json.JSONDecodeError, ValueError):
                errors[CONF_SLOT_OVERRIDES] = "invalid_json"
            else:
                return self.async_create_entry(
                    title="",
                    data={**user_input, CONF_SLOT_OVERRIDES: slot_overrides},
                )
        opts = self.config_entry.options
        data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))): vol.All(int, vol.Range(min=3, max=60)),
                vol.Required(CONF_COMMAND_TIMEOUT, default=opts.get(CONF_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT)): vol.All(float, vol.Range(min=2, max=60)),
                vol.Required(CONF_COMMAND_RETRIES, default=opts.get(CONF_COMMAND_RETRIES, DEFAULT_COMMAND_RETRIES)): vol.All(int, vol.Range(min=0, max=3)),
                vol.Required(CONF_BUTTON_DELAY, default=opts.get(CONF_BUTTON_DELAY, DEFAULT_BUTTON_DELAY)): vol.All(float, vol.Range(min=0.25, max=5)),
                vol.Required(CONF_SLOT_OVERRIDES, default=_slot_overrides_to_text(opts.get(CONF_SLOT_OVERRIDES, {}))): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
