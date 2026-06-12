from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AquaConnectClient, AquaConnectError, CommandResult
from .const import CONF_BUTTON_DELAY, CONF_COMMAND_RETRIES, CONF_COMMAND_TIMEOUT, DEFAULT_BUTTON_DELAY, DEFAULT_COMMAND_RETRIES, DEFAULT_COMMAND_TIMEOUT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .parser import merge_status

_LOGGER = logging.getLogger(__name__)


class AquaConnectCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        host = entry.data["host"]
        self.client = AquaConnectClient(async_get_clientsession(hass), host)
        self.last_command_result: dict[str, Any] | None = None
        self.last_command_error: str | None = None
        scan_interval = entry.options.get("scan_interval", entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.client.async_read_status()
            return merge_status(self.data or {}, status)
        except AquaConnectError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_switch(self, slug: str, desired_on: bool) -> CommandResult:
        retries = int(self.entry.options.get(CONF_COMMAND_RETRIES, DEFAULT_COMMAND_RETRIES))
        timeout = float(self.entry.options.get(CONF_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT))
        delay = float(self.entry.options.get(CONF_BUTTON_DELAY, DEFAULT_BUTTON_DELAY))
        try:
            result = await self.client.async_set_slot_state(
                slug,
                desired_on,
                retries=retries,
                verify_timeout=timeout,
                button_delay=delay,
            )
            self.last_command_result = result.__dict__
            self.last_command_error = None
            await self.async_request_refresh()
            return result
        except Exception as err:
            self.last_command_error = str(err)
            self.last_command_result = None
            await self.async_request_refresh()
            raise
