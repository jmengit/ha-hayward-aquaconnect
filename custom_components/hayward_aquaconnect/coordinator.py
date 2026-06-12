from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AquaConnectClient, AquaConnectError, CommandResult
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
from .parser import merge_status
from .slots import EquipmentSlot, resolve_equipment_slots

_LOGGER = logging.getLogger(__name__)
_MAX_FAILURES_BEFORE_STALE = 4
_FAILURE_2_COOLDOWN_FACTOR = 2
_FAILURE_3_COOLDOWN_FACTOR = 4


class AquaConnectCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        host = entry.data["host"]
        self.client = AquaConnectClient(async_get_clientsession(hass), host)
        self.last_command_result: dict[str, Any] | None = None
        self.last_command_error: str | None = None
        self.last_successful_read: datetime | None = None
        self.last_read_error: str | None = None
        self.consecutive_failures = 0
        self.cooldown_until: datetime | None = None
        self.equipment_slots: tuple[EquipmentSlot, ...] = resolve_equipment_slots(entry.options.get(CONF_SLOT_OVERRIDES))
        self.equipment_slots_by_slug = {slot.slug: slot for slot in self.equipment_slots}
        self.used_slots = tuple(slot for slot in self.equipment_slots if slot.used_default)
        self.switch_slots = tuple(slot for slot in self.equipment_slots if slot.enable_switch)
        self.scan_interval = float(entry.options.get("scan_interval", entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
        )

    def _cooldown_for_failure(self, failures: int) -> timedelta | None:
        if failures == 2:
            return timedelta(seconds=self.scan_interval * _FAILURE_2_COOLDOWN_FACTOR)
        if failures == 3:
            return timedelta(seconds=self.scan_interval * _FAILURE_3_COOLDOWN_FACTOR)
        return None

    def _read_status_state(self) -> str:
        if self.last_successful_read is None:
            return "starting"
        if self.consecutive_failures >= _MAX_FAILURES_BEFORE_STALE:
            return "stale"
        if self.consecutive_failures >= 2:
            return "cooldown"
        if self.consecutive_failures == 1:
            return "degraded"
        return "healthy"

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        if self.cooldown_until and now < self.cooldown_until:
            _LOGGER.debug("AquaConnect read cooldown active until %s", self.cooldown_until.isoformat())
            if self.data is None:
                raise UpdateFailed("AquaConnect is cooling down before first successful read")
            return self.data

        try:
            status = await self.client.async_read_status(self.equipment_slots)
        except AquaConnectError as err:
            self.consecutive_failures += 1
            self.last_read_error = str(err)
            _LOGGER.warning(
                "AquaConnect read failed (%s consecutive failures): %s",
                self.consecutive_failures,
                err,
            )
            cooldown = self._cooldown_for_failure(self.consecutive_failures)
            if cooldown is not None:
                self.cooldown_until = now + cooldown
            if self.data is None or self.consecutive_failures >= _MAX_FAILURES_BEFORE_STALE:
                raise UpdateFailed(str(err)) from err
            return self.data

        self.consecutive_failures = 0
        self.cooldown_until = None
        self.last_read_error = None
        self.last_successful_read = now
        return merge_status(self.data or {}, status)

    async def async_set_switch(self, slug: str, desired_on: bool) -> CommandResult:
        retries = int(self.entry.options.get(CONF_COMMAND_RETRIES, DEFAULT_COMMAND_RETRIES))
        timeout = float(self.entry.options.get(CONF_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT))
        delay = float(self.entry.options.get(CONF_BUTTON_DELAY, DEFAULT_BUTTON_DELAY))
        try:
            result = await self.client.async_set_slot_state(
                slug,
                desired_on,
                slots=self.equipment_slots,
                slots_by_slug=self.equipment_slots_by_slug,
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
