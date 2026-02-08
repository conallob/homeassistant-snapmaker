"""Binary sensor platform for Snapmaker integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Snapmaker binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]

    entities = [
        SnapmakerFilamentOutBinarySensor(coordinator, device),
        SnapmakerDoorOpenBinarySensor(coordinator, device),
        SnapmakerEnclosureBinarySensor(coordinator, device),
        SnapmakerRotaryModuleBinarySensor(coordinator, device),
        SnapmakerEmergencyStopBinarySensor(coordinator, device),
        SnapmakerAirPurifierBinarySensor(coordinator, device),
    ]

    async_add_entities(entities)


class SnapmakerBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for Snapmaker binary sensors."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
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


class SnapmakerFilamentOutBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker filament runout binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Filament Runout"
        self._attr_unique_id = f"{self._device.host}_filament_out"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:printer-3d-nozzle-alert"

    @property
    def is_on(self) -> bool:
        """Return true if filament has run out."""
        return self._device.data.get("is_filament_out", False)


class SnapmakerDoorOpenBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker enclosure door binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Door"
        self._attr_unique_id = f"{self._device.host}_door_open"
        self._attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the door is open."""
        return self._device.data.get("is_door_open", False)


class SnapmakerEnclosureBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker enclosure presence binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Enclosure"
        self._attr_unique_id = f"{self._device.host}_enclosure"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:cube-outline"

    @property
    def is_on(self) -> bool:
        """Return true if enclosure is connected."""
        return self._device.data.get("has_enclosure", False)


class SnapmakerRotaryModuleBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker rotary module presence binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Rotary Module"
        self._attr_unique_id = f"{self._device.host}_rotary_module"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:rotate-3d-variant"

    @property
    def is_on(self) -> bool:
        """Return true if rotary module is connected."""
        return self._device.data.get("has_rotary_module", False)


class SnapmakerEmergencyStopBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker emergency stop presence binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Emergency Stop Button"
        self._attr_unique_id = f"{self._device.host}_emergency_stop"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        self._attr_icon = "mdi:stop-circle"

    @property
    def is_on(self) -> bool:
        """Return true if emergency stop button is connected."""
        return self._device.data.get("has_emergency_stop", False)


class SnapmakerAirPurifierBinarySensor(SnapmakerBinarySensorBase):
    """Representation of a Snapmaker air purifier presence binary sensor."""

    def __init__(self, coordinator, device):
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Air Purifier"
        self._attr_unique_id = f"{self._device.host}_air_purifier"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"

    @property
    def is_on(self) -> bool:
        """Return true if air purifier is connected."""
        return self._device.data.get("has_air_purifier", False)
