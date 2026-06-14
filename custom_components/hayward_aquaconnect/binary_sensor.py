from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquaConnectEntity
from .slots import EquipmentSlot


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AquaConnectDisplayAlertBinarySensor(coordinator),
            AquaConnectConnectionAlertBinarySensor(coordinator),
            AquaConnectSuperChlorinateBinarySensor(coordinator),
        ]
        + [AquaConnectEquipmentBinarySensor(coordinator, slot) for slot in coordinator.used_slots]
    )


class AquaConnectDisplayAlertBinarySensor(AquaConnectEntity, BinarySensorEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.data['host']}_display_alert"
        self._attr_name = "Display Alert"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("display_alert"))

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        data = self.coordinator.data or {}
        attrs.update(
            {
                "message": data.get("display_alert"),
                "candidate_message": data.get("display_alert_candidate"),
                "candidate_since": data.get("display_alert_candidate_since"),
                "candidate_last_seen": data.get("display_alert_candidate_last_seen"),
                "candidate_observations": data.get("display_alert_observations"),
                "confirmation_seconds": data.get("display_alert_confirmation_seconds"),
                "clear_after_seconds": data.get("display_alert_clear_after_seconds"),
                "display_message": data.get("display_message"),
                "display_page_kind": data.get("display_page_kind"),
                "display_line_1": data.get("display_line_1"),
                "display_line_2": data.get("display_line_2"),
            }
        )
        return attrs


class AquaConnectConnectionAlertBinarySensor(AquaConnectEntity, BinarySensorEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.data['host']}_connection_alert"
        self._attr_name = "Connection Alert"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.coordinator._read_status_state() != "healthy"

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        attrs.update(
            {
                "read_health": self.coordinator._read_status_state(),
                "last_successful_read": self.coordinator.last_successful_read.isoformat()
                if self.coordinator.last_successful_read
                else None,
                "consecutive_failures": self.coordinator.consecutive_failures,
                "cooldown_until": self.coordinator.cooldown_until.isoformat() if self.coordinator.cooldown_until else None,
                "last_read_error": self.coordinator.last_read_error,
            }
        )
        return attrs


class AquaConnectSuperChlorinateBinarySensor(AquaConnectEntity, BinarySensorEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.data['host']}_super_chlorinate"
        self._attr_name = "Super Chlorinate"
        self._attr_device_class = getattr(BinarySensorDeviceClass, "RUNNING", None)

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get("super_chlorinate_running"))

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes or {}
        data = self.coordinator.data or {}
        attrs.update({"time_remaining_minutes": data.get("super_chlorinate_time_remaining")})
        return attrs


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
