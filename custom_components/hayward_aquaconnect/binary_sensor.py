from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquaConnectEntity
from .slots import EquipmentSlot


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AquaConnectEquipmentBinarySensor(coordinator, slot) for slot in coordinator.used_slots)


class AquaConnectEquipmentBinarySensor(AquaConnectEntity, BinarySensorEntity):
    def __init__(self, coordinator, slot: EquipmentSlot) -> None:
        super().__init__(coordinator)
        self.slot = slot
        self._attr_unique_id = f"{coordinator.entry.data['host']}_{slot.slug}_status"
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
        attrs.update({"raw_state": equipment.get("state"), "key_index": self.slot.key_index})
        return attrs
