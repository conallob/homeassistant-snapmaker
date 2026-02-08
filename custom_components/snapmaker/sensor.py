"""Sensor platform for Snapmaker integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
)
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
    """Set up Snapmaker sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = hass.data[DOMAIN][entry.entry_id]["device"]

    # Common sensors for all devices
    entities = [
        SnapmakerStatusSensor(coordinator, device),
        SnapmakerBedTempSensor(coordinator, device),
        SnapmakerBedTargetTempSensor(coordinator, device),
        SnapmakerFileNameSensor(coordinator, device),
        SnapmakerProgressSensor(coordinator, device),
        SnapmakerElapsedTimeSensor(coordinator, device),
        SnapmakerRemainingTimeSensor(coordinator, device),
        SnapmakerEstimatedTimeSensor(coordinator, device),
        SnapmakerToolHeadSensor(coordinator, device),
        SnapmakerPositionXSensor(coordinator, device),
        SnapmakerPositionYSensor(coordinator, device),
        SnapmakerPositionZSensor(coordinator, device),
        SnapmakerHomingSensor(coordinator, device),
        SnapmakerFilamentOutSensor(coordinator, device),
        SnapmakerDoorOpenSensor(coordinator, device),
        SnapmakerEnclosureSensor(coordinator, device),
        SnapmakerRotaryModuleSensor(coordinator, device),
        SnapmakerEmergencyStopSensor(coordinator, device),
        SnapmakerAirPurifierSensor(coordinator, device),
        SnapmakerTotalLinesSensor(coordinator, device),
        SnapmakerCurrentLineSensor(coordinator, device),
        SnapmakerDiagnosticSensor(coordinator, device),
    ]

    # Add nozzle sensors based on extruder configuration
    if device.dual_extruder:
        entities.extend(
            [
                SnapmakerNozzle1TempSensor(coordinator, device),
                SnapmakerNozzle1TargetTempSensor(coordinator, device),
                SnapmakerNozzle2TempSensor(coordinator, device),
                SnapmakerNozzle2TargetTempSensor(coordinator, device),
            ]
        )
    else:
        entities.extend(
            [
                SnapmakerNozzleTempSensor(coordinator, device),
                SnapmakerNozzleTargetTempSensor(coordinator, device),
            ]
        )

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


# --- Status ---


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


# --- Temperature sensors ---


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


class SnapmakerNozzle1TempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle 1 temperature sensor (dual extruder)."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 1 Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle1_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle1_temperature", 0)


class SnapmakerNozzle1TargetTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle 1 target temperature sensor (dual extruder)."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 1 Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle1_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle1_target_temperature", 0)


class SnapmakerNozzle2TempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle 2 temperature sensor (dual extruder)."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 2 Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle2_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle2_temperature", 0)


class SnapmakerNozzle2TargetTempSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker nozzle 2 target temperature sensor (dual extruder)."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 2 Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle2_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("nozzle2_target_temperature", 0)


# --- Print job sensors ---


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


class SnapmakerEstimatedTimeSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker estimated total time sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Estimated Time"
        self._attr_unique_id = f"{self._device.host}_estimated_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-start"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("estimated_time", "00:00:00")


class SnapmakerTotalLinesSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker total G-code lines sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Total G-code Lines"
        self._attr_unique_id = f"{self._device.host}_total_lines"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:code-braces"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._device.data.get("total_lines", 0)


class SnapmakerCurrentLineSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker current G-code line sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Current G-code Line"
        self._attr_unique_id = f"{self._device.host}_current_line"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:code-braces"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._device.data.get("current_line", 0)


# --- Toolhead and position sensors ---


class SnapmakerToolHeadSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker tool head sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Tool Head"
        self._attr_unique_id = f"{self._device.host}_tool_head"
        self._attr_icon = "mdi:toolbox"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("tool_head", "N/A")


class SnapmakerPositionXSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker X position sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Position X"
        self._attr_unique_id = f"{self._device.host}_position_x"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-x-arrow"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("x", 0)


class SnapmakerPositionYSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker Y position sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Position Y"
        self._attr_unique_id = f"{self._device.host}_position_y"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-y-arrow"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("y", 0)


class SnapmakerPositionZSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker Z position sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Position Z"
        self._attr_unique_id = f"{self._device.host}_position_z"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-z-arrow"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._device.data.get("z", 0)


class SnapmakerHomingSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker homing state sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Homing"
        self._attr_unique_id = f"{self._device.host}_homing"
        self._attr_icon = "mdi:home-map-marker"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._device.data.get("homing", "N/A")


# --- Module and safety sensors ---


class SnapmakerFilamentOutSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker filament runout sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Filament Runout"
        self._attr_unique_id = f"{self._device.host}_filament_out"
        self._attr_icon = "mdi:printer-3d-nozzle-alert"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return "Yes" if self._device.data.get("is_filament_out", False) else "No"


class SnapmakerDoorOpenSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker enclosure door sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Door Open"
        self._attr_unique_id = f"{self._device.host}_door_open"
        self._attr_icon = "mdi:door-open"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return "Open" if self._device.data.get("is_door_open", False) else "Closed"

    @property
    def icon(self) -> str:
        """Return the icon based on door state."""
        if self._device.data.get("is_door_open", False):
            return "mdi:door-open"
        return "mdi:door-closed"


class SnapmakerEnclosureSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker enclosure presence sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Enclosure"
        self._attr_unique_id = f"{self._device.host}_enclosure"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:cube-outline"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return (
            "Connected"
            if self._device.data.get("has_enclosure", False)
            else "Not Connected"
        )


class SnapmakerRotaryModuleSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker rotary module presence sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Rotary Module"
        self._attr_unique_id = f"{self._device.host}_rotary_module"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:rotate-3d-variant"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return (
            "Connected"
            if self._device.data.get("has_rotary_module", False)
            else "Not Connected"
        )


class SnapmakerEmergencyStopSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker emergency stop presence sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Emergency Stop Button"
        self._attr_unique_id = f"{self._device.host}_emergency_stop"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:stop-circle"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return (
            "Connected"
            if self._device.data.get("has_emergency_stop", False)
            else "Not Connected"
        )


class SnapmakerAirPurifierSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker air purifier presence sensor."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "Air Purifier"
        self._attr_unique_id = f"{self._device.host}_air_purifier"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:air-filter"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return (
            "Connected"
            if self._device.data.get("has_air_purifier", False)
            else "Not Connected"
        )


# --- Diagnostic sensor with raw API response ---


class SnapmakerDiagnosticSensor(SnapmakerSensorBase):
    """Diagnostic sensor exposing the raw API response as extra attributes."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self._attr_name = "API Response"
        self._attr_unique_id = f"{self._device.host}_api_response"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:api"

    @property
    def state(self) -> str:
        """Return the device status as the primary state."""
        return self._device.status

    @property
    def extra_state_attributes(self) -> dict:
        """Return the full raw API response as extra attributes."""
        return self._device.raw_api_response
