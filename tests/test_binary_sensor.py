from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from datetime import UTC, datetime


if "homeassistant" not in sys.modules:
    ha = ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha
else:
    ha = sys.modules["homeassistant"]

components = sys.modules.setdefault("homeassistant.components", ModuleType("homeassistant.components"))
binary_sensor_mod = sys.modules.setdefault(
    "homeassistant.components.binary_sensor", ModuleType("homeassistant.components.binary_sensor")
)
config_entries = sys.modules.setdefault("homeassistant.config_entries", ModuleType("homeassistant.config_entries"))
core = sys.modules.setdefault("homeassistant.core", ModuleType("homeassistant.core"))
helpers = sys.modules.setdefault("homeassistant.helpers", ModuleType("homeassistant.helpers"))
entity_platform = sys.modules.setdefault(
    "homeassistant.helpers.entity_platform", ModuleType("homeassistant.helpers.entity_platform")
)
device_registry = sys.modules.setdefault(
    "homeassistant.helpers.device_registry", ModuleType("homeassistant.helpers.device_registry")
)
update_coordinator = sys.modules.setdefault(
    "homeassistant.helpers.update_coordinator", ModuleType("homeassistant.helpers.update_coordinator")
)
aiohttp_client = sys.modules.setdefault(
    "homeassistant.helpers.aiohttp_client", ModuleType("homeassistant.helpers.aiohttp_client")
)


class BinarySensorDeviceClass:  # pragma: no cover - import stub
    PROBLEM = "problem"


class BinarySensorEntity:  # pragma: no cover - import stub
    pass


class ConfigEntry:  # pragma: no cover - import stub
    pass


class HomeAssistant:  # pragma: no cover - import stub
    pass


class DeviceInfo(dict):  # pragma: no cover - import stub
    pass


class CoordinatorEntity:  # pragma: no cover - import stub
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls

    @property
    def extra_state_attributes(self):
        return {}


class DataUpdateCoordinator:  # pragma: no cover - import stub
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None

    def __class_getitem__(cls, item):
        return cls

    async def async_request_refresh(self):
        self.data = await self._async_update_data()  # type: ignore[attr-defined]
        return self.data


class UpdateFailed(Exception):
    pass


def async_get_clientsession(hass):  # pragma: no cover - import stub
    return getattr(hass, "session", None)


setattr(binary_sensor_mod, "BinarySensorDeviceClass", BinarySensorDeviceClass)
setattr(binary_sensor_mod, "BinarySensorEntity", BinarySensorEntity)
setattr(config_entries, "ConfigEntry", ConfigEntry)
setattr(core, "HomeAssistant", HomeAssistant)
setattr(entity_platform, "AddEntitiesCallback", object)
setattr(device_registry, "DeviceInfo", DeviceInfo)
setattr(update_coordinator, "CoordinatorEntity", CoordinatorEntity)
setattr(update_coordinator, "DataUpdateCoordinator", DataUpdateCoordinator)
setattr(update_coordinator, "UpdateFailed", UpdateFailed)
setattr(aiohttp_client, "async_get_clientsession", async_get_clientsession)
setattr(ha, "components", components)
setattr(ha, "config_entries", config_entries)
setattr(ha, "core", core)
setattr(ha, "helpers", helpers)


from custom_components.hayward_aquaconnect.binary_sensor import (  # noqa: E402
    AquaConnectConnectionAlertBinarySensor,
    AquaConnectDisplayAlertBinarySensor,
)


class FakeCoordinator:
    def __init__(self, *, failures: int = 0, data: dict | None = None, starting: bool = False) -> None:
        self.entry = SimpleNamespace(data={"host": "192.0.2.10"})
        self.consecutive_failures = failures
        self.last_read_error = "read failed" if failures else None
        self.cooldown_until = None
        self.last_successful_read = None if starting else datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
        self.last_command_result = None
        self.last_command_error = None
        self.data = data or {}

    def _read_status_state(self) -> str:
        if self.last_successful_read is None:
            return "starting"
        if self.consecutive_failures >= 4:
            return "stale"
        if self.consecutive_failures >= 2:
            return "cooldown"
        if self.consecutive_failures == 1:
            return "degraded"
        return "healthy"


def test_connection_alert_binary_sensor_is_off_when_reads_are_healthy():
    sensor = AquaConnectConnectionAlertBinarySensor(FakeCoordinator(failures=0))

    assert sensor.is_on is False
    assert sensor.extra_state_attributes["read_health"] == "healthy"


def test_connection_alert_binary_sensor_is_on_before_first_successful_read():
    sensor = AquaConnectConnectionAlertBinarySensor(FakeCoordinator(starting=True))

    assert sensor.is_on is True
    assert sensor.extra_state_attributes["read_health"] == "starting"


def test_connection_alert_binary_sensor_is_on_when_reads_are_not_succeeding():
    for failures, health in ((1, "degraded"), (2, "cooldown"), (4, "stale")):
        sensor = AquaConnectConnectionAlertBinarySensor(FakeCoordinator(failures=failures))

        assert sensor.is_on is True
        assert sensor.extra_state_attributes["read_health"] == health
        assert sensor.extra_state_attributes["consecutive_failures"] == failures


def test_display_alert_binary_sensor_remains_simple_problem_sensor():
    sensor = AquaConnectDisplayAlertBinarySensor(FakeCoordinator(data={"display_alert": "No Flow / Check System"}))

    assert sensor.is_on is True
    assert sensor.extra_state_attributes["message"] == "No Flow / Check System"
