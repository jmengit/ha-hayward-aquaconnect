from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import AquaConnectCommandError
from .const import DOMAIN
from .entity import AquaConnectEntity
from .slots import SWITCH_SLOTS, EquipmentSlot


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AquaConnectEquipmentSwitch(coordinator, slot) for slot in SWITCH_SLOTS)


class AquaConnectEquipmentSwitch(AquaConnectEntity, SwitchEntity):
    def __init__(self, coordinator, slot: EquipmentSlot) -> None:
        super().__init__(coordinator)
        self.slot = slot
        self._attr_unique_id = f"{coordinator.entry.data['host']}_{slot.slug}_switch"
        self._attr_name = slot.name

    @property
    def is_on(self) -> bool | None:
        state = ((self.coordinator.data or {}).get("equipment") or {}).get(self.slot.slug, {}).get("state")
        if state == "on":
            return True
        if state == "off":
            return False
        return None

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        equipment = ((self.coordinator.data or {}).get("equipment") or {}).get(self.slot.slug, {})
        attrs.update(
            {
                "raw_state": equipment.get("state"),
                "key_index": self.slot.key_index,
                "press_key_id": self.slot.press_key_id,
                "command_verification": "press, poll until desired state, retry per options, raise error if unverified",
            }
        )
        return attrs

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)

    async def _set_state(self, desired_on: bool) -> None:
        try:
            await self.coordinator.async_set_switch(self.slot.slug, desired_on)
        except AquaConnectCommandError as err:
            raise HomeAssistantError(f"AquaConnect command failed for {self.slot.name}: {err}") from err
        except Exception as err:
            raise HomeAssistantError(f"AquaConnect command error for {self.slot.name}: {err}") from err
