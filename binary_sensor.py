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
        SnapmakerHomedBinarySensor(coordinator, device),
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
        super().__init__(coordinator)
        self._device = device
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device.host)},
            "name": f"Snapmaker {self._device.model or self._device.host}",
            "manufacturer": "Snapmaker",
            "model": self._device.model,
            "sw_version": None,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class SnapmakerHomedBinarySensor(SnapmakerBinarySensorBase):
    """True when the printer has been homed."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Homed"
        self._attr_unique_id = f"{self._device.host}_homed"
        self._attr_icon = "mdi:home-import-outline"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("homed", False))


class SnapmakerFilamentOutBinarySensor(SnapmakerBinarySensorBase):
    """True when filament has run out."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Filament Runout"
        self._attr_unique_id = f"{self._device.host}_filament_out"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:printer-3d-nozzle-alert"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("is_filament_out", False))


class SnapmakerDoorOpenBinarySensor(SnapmakerBinarySensorBase):
    """True when the enclosure door is open."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Door"
        self._attr_unique_id = f"{self._device.host}_door_open"
        self._attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("is_door_open", False))


class SnapmakerEnclosureBinarySensor(SnapmakerBinarySensorBase):
    """True when enclosure is connected."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Enclosure"
        self._attr_unique_id = f"{self._device.host}_enclosure"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:cube-outline"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("has_enclosure", False))


class SnapmakerRotaryModuleBinarySensor(SnapmakerBinarySensorBase):
    """True when rotary module is connected."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Rotary Module"
        self._attr_unique_id = f"{self._device.host}_rotary_module"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:rotate-3d-variant"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("has_rotary_module", False))


class SnapmakerEmergencyStopBinarySensor(SnapmakerBinarySensorBase):
    """True when emergency stop button is connected."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Emergency Stop Button"
        self._attr_unique_id = f"{self._device.host}_emergency_stop"
        self._attr_device_class = BinarySensorDeviceClass.SAFETY
        self._attr_icon = "mdi:stop-circle"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("has_emergency_stop", False))


class SnapmakerAirPurifierBinarySensor(SnapmakerBinarySensorBase):
    """True when air purifier is connected."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Air Purifier"
        self._attr_unique_id = f"{self._device.host}_air_purifier"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"

    @property
    def is_on(self) -> bool:
        return bool(self._device.data.get("has_air_purifier", False))
