from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, MODEL
from .coordinator import AquaConnectCoordinator


class AquaConnectEntity(CoordinatorEntity[AquaConnectCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AquaConnectCoordinator) -> None:
        super().__init__(coordinator)
        host = coordinator.entry.data["host"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=DEFAULT_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=f"http://{host}/",
        )

    @property
    def extra_state_attributes(self):
        attrs = {}
        if self.coordinator.last_command_result:
            attrs["last_command_result"] = self.coordinator.last_command_result
        if self.coordinator.last_command_error:
            attrs["last_command_error"] = self.coordinator.last_command_error
        return attrs
