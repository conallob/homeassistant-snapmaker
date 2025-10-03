"""Sensor platform for Snapmaker integration."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from typing import Any, Callable, Dict, List, Optional

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Snapmaker sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]

    entities = [
        SnapmakerStatusSensor(coordinator, device),
        SnapmakerNozzleTempSensor(coordinator, device),
        SnapmakerNozzleTargetTempSensor(coordinator, device),
        SnapmakerBedTempSensor(coordinator, device),
        SnapmakerBedTargetTempSensor(coordinator, device),
        SnapmakerFileNameSensor(coordinator, device),
        SnapmakerProgressSensor(coordinator, device),
        SnapmakerElapsedTimeSensor(coordinator, device),
        SnapmakerRemainingTimeSensor(coordinator, device),
    ]

    async_add_entities(entities)


class SnapmakerSensorBase(CoordinatorEntity):
    """Base class for Snapmaker sensors."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        """Return device information about this Snapmaker device."""
        return {
            "identifiers": {(DOMAIN, self._device.host)},
            "name": f"Snapmaker {self._device.model or self._device.host}",
            "manufacturer": "Snapmaker",
            "model": self._device.model,
            "sw_version": None,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._device.available


class SnapmakerStatusSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker status sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Status"
        self._attr_unique_id = f"{self._device.host}_status"
        self._attr_icon = "mdi:printer-3d"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.status


class SnapmakerNozzleTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle temperature sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle_temperature", 0)


class SnapmakerNozzleTargetTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle target temperature sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle_target_temperature", 0)


class SnapmakerBedTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker bed temperature sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Bed Temperature"
        self._attr_unique_id = f"{self._device.host}_bed_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("heated_bed_temperature", 0)


class SnapmakerBedTargetTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker bed target temperature sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Bed Target Temperature"
        self._attr_unique_id = f"{self._device.host}_bed_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("heated_bed_target_temperature", 0)


class SnapmakerFileNameSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker file name sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "File Name"
        self._attr_unique_id = f"{self._device.host}_file_name"
        self._attr_icon = "mdi:file-document"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("file_name", "N/A")


class SnapmakerProgressSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker progress sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Progress"
        self._attr_unique_id = f"{self._device.host}_progress"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:progress-check"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("progress", 0)


class SnapmakerElapsedTimeSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker elapsed time sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Elapsed Time"
        self._attr_unique_id = f"{self._device.host}_elapsed_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-outline"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("elapsed_time", "00:00:00")


class SnapmakerRemainingTimeSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker remaining time sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Remaining Time"
        self._attr_unique_id = f"{self._device.host}_remaining_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-end"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("remaining_time", "00:00:00")
