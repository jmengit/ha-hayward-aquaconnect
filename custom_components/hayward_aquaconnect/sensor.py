from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import AquaConnectEntity


@dataclass(frozen=True, kw_only=True)
class AquaConnectSensorDescription(SensorEntityDescription):
    data_key: str


SENSORS: tuple[AquaConnectSensorDescription, ...] = (
    AquaConnectSensorDescription(
        key="pool_temperature",
        translation_key="pool_temperature",
        name="Pool Temperature",
        data_key="pool_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AquaConnectSensorDescription(
        key="air_temperature",
        translation_key="air_temperature",
        name="Air Temperature",
        data_key="air_temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AquaConnectSensorDescription(
        key="salt_level",
        translation_key="salt_level",
        name="Salt Level",
        data_key="salt_level",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AquaConnectSensorDescription(
        key="chlorinator_percent",
        translation_key="chlorinator_percent",
        name="Chlorinator Percent",
        data_key="chlorinator_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AquaConnectSensorDescription(key="display_line_1", name="Display Line 1", data_key="display_line_1"),
    AquaConnectSensorDescription(key="display_line_2", name="Display Line 2", data_key="display_line_2"),
    AquaConnectSensorDescription(key="raw_leds", name="Raw LEDs", data_key="raw_leds"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AquaConnectSensor(coordinator, description) for description in SENSORS)


class AquaConnectSensor(AquaConnectEntity, SensorEntity):
    entity_description: AquaConnectSensorDescription

    def __init__(self, coordinator, description: AquaConnectSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.data['host']}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data or {}).get(self.entity_description.data_key)
