from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import AquaConnectClient, AquaConnectError
from .const import CONF_BUTTON_DELAY, CONF_COMMAND_RETRIES, CONF_COMMAND_TIMEOUT, DEFAULT_BUTTON_DELAY, DEFAULT_COMMAND_RETRIES, DEFAULT_COMMAND_TIMEOUT, DEFAULT_SCAN_INTERVAL, DOMAIN


class AquaConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
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
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.1.50"): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=3, max=60)),
                vol.Required(CONF_COMMAND_TIMEOUT, default=DEFAULT_COMMAND_TIMEOUT): vol.All(float, vol.Range(min=2, max=60)),
                vol.Required(CONF_COMMAND_RETRIES, default=DEFAULT_COMMAND_RETRIES): vol.All(int, vol.Range(min=0, max=3)),
                vol.Required(CONF_BUTTON_DELAY, default=DEFAULT_BUTTON_DELAY): vol.All(float, vol.Range(min=0.25, max=5)),
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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self.config_entry.options
        data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))): vol.All(int, vol.Range(min=3, max=60)),
                vol.Required(CONF_COMMAND_TIMEOUT, default=opts.get(CONF_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT)): vol.All(float, vol.Range(min=2, max=60)),
                vol.Required(CONF_COMMAND_RETRIES, default=opts.get(CONF_COMMAND_RETRIES, DEFAULT_COMMAND_RETRIES)): vol.All(int, vol.Range(min=0, max=3)),
                vol.Required(CONF_BUTTON_DELAY, default=opts.get(CONF_BUTTON_DELAY, DEFAULT_BUTTON_DELAY)): vol.All(float, vol.Range(min=0.25, max=5)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
