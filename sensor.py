"""Sensor platform for Snapmaker integration."""

from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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

from .const import DOMAIN, TOOLHEAD_TYPE_CNC, TOOLHEAD_TYPE_LASER

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
        SnapmakerPrintStatusSensor(coordinator, device),
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
        SnapmakerOffsetXSensor(coordinator, device),
        SnapmakerOffsetYSensor(coordinator, device),
        SnapmakerOffsetZSensor(coordinator, device),
        SnapmakerWorkSpeedSensor(coordinator, device),
        SnapmakerTotalLinesSensor(coordinator, device),
        SnapmakerCurrentLineSensor(coordinator, device),
        SnapmakerDiagnosticSensor(coordinator, device),
    ]

    tool_head = device.toolhead_type
    if tool_head is None:
        _LOGGER.debug(
            "Toolhead type unknown for %s; CNC/Laser sensors will not be "
            "created. Reload the integration after the device comes online",
            device.host,
        )
    if tool_head == TOOLHEAD_TYPE_CNC:
        entities.append(SnapmakerSpindleSpeedSensor(coordinator, device))
    if tool_head == TOOLHEAD_TYPE_LASER:
        entities.extend(
            [
                SnapmakerLaserPowerSensor(coordinator, device),
                SnapmakerLaserFocalLengthSensor(coordinator, device),
            ]
        )

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


class SnapmakerSensorBase(CoordinatorEntity, SensorEntity):
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
        return self.coordinator.last_update_success


# --- Status ---


class SnapmakerStatusSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker status sensor."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Status"
        self._attr_unique_id = f"{self._device.host}_status"
        self._attr_icon = "mdi:printer-3d"

    @property
    def state(self) -> str:
        return self._device.status


class SnapmakerPrintStatusSensor(SnapmakerSensorBase):
    """Representation of a Snapmaker print status sensor (e.g. Printing, Paused)."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Print Status"
        self._attr_unique_id = f"{self._device.host}_print_status"
        self._attr_icon = "mdi:printer-3d"

    @property
    def state(self) -> Optional[str]:
        return self._device.data.get("print_status")


# --- Temperature sensors ---


class SnapmakerNozzleTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle_temperature")


class SnapmakerNozzleTargetTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle_target_temperature")


class SnapmakerBedTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Bed Temperature"
        self._attr_unique_id = f"{self._device.host}_bed_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("heated_bed_temperature")


class SnapmakerBedTargetTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Bed Target Temperature"
        self._attr_unique_id = f"{self._device.host}_bed_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("heated_bed_target_temperature")


class SnapmakerNozzle1TempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 1 Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle1_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle1_temperature")


class SnapmakerNozzle1TargetTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 1 Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle1_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle1_target_temperature")


class SnapmakerNozzle2TempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 2 Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle2_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle2_temperature")


class SnapmakerNozzle2TargetTempSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Nozzle 2 Target Temperature"
        self._attr_unique_id = f"{self._device.host}_nozzle2_target_temp"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("nozzle2_target_temperature")


# --- Print job sensors ---


class SnapmakerFileNameSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "File Name"
        self._attr_unique_id = f"{self._device.host}_file_name"
        self._attr_icon = "mdi:file-document"

    @property
    def state(self) -> str:
        return self._device.data.get("file_name", "N/A")


class SnapmakerProgressSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Progress"
        self._attr_unique_id = f"{self._device.host}_progress"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:progress-check"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("progress")


class SnapmakerElapsedTimeSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Elapsed Time"
        self._attr_unique_id = f"{self._device.host}_elapsed_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-outline"

    @property
    def state(self) -> str:
        return self._device.data.get("elapsed_time", "00:00:00")


class SnapmakerRemainingTimeSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Remaining Time"
        self._attr_unique_id = f"{self._device.host}_remaining_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-end"

    @property
    def state(self) -> str:
        return self._device.data.get("remaining_time", "00:00:00")


class SnapmakerEstimatedTimeSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Estimated Time"
        self._attr_unique_id = f"{self._device.host}_estimated_time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_icon = "mdi:clock-start"

    @property
    def state(self) -> str:
        return self._device.data.get("estimated_time", "00:00:00")


class SnapmakerTotalLinesSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Total G-code Lines"
        self._attr_unique_id = f"{self._device.host}_total_lines"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:code-braces"

    @property
    def native_value(self) -> Optional[int]:
        return self._device.data.get("total_lines")


class SnapmakerCurrentLineSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Current G-code Line"
        self._attr_unique_id = f"{self._device.host}_current_line"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:code-braces"

    @property
    def native_value(self) -> Optional[int]:
        return self._device.data.get("current_line")


class SnapmakerWorkSpeedSensor(SnapmakerSensorBase):
    """Work speed in mm/min."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Work Speed"
        self._attr_unique_id = f"{self._device.host}_work_speed"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "mm/min"
        self._attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("work_speed")


# --- Toolhead and position sensors ---


class SnapmakerToolHeadSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Tool Head"
        self._attr_unique_id = f"{self._device.host}_tool_head"
        self._attr_icon = "mdi:toolbox"

    @property
    def state(self) -> str:
        return self._device.data.get("tool_head", "N/A")


class SnapmakerPositionXSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Position X"
        self._attr_unique_id = f"{self._device.host}_position_x"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-x-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("x")


class SnapmakerPositionYSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Position Y"
        self._attr_unique_id = f"{self._device.host}_position_y"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-y-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("y")


class SnapmakerPositionZSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Position Z"
        self._attr_unique_id = f"{self._device.host}_position_z"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:axis-z-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("z")


class SnapmakerOffsetXSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Offset X"
        self._attr_unique_id = f"{self._device.host}_offset_x"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:axis-x-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("offset_x")


class SnapmakerOffsetYSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Offset Y"
        self._attr_unique_id = f"{self._device.host}_offset_y"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:axis-y-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("offset_y")


class SnapmakerOffsetZSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Offset Z"
        self._attr_unique_id = f"{self._device.host}_offset_z"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:axis-z-arrow"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("offset_z")


# --- CNC/Laser sensors ---


class SnapmakerSpindleSpeedSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Spindle Speed"
        self._attr_unique_id = f"{self._device.host}_spindle_speed"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "RPM"
        self._attr_icon = "mdi:rotate-right"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("spindle_speed")


class SnapmakerLaserPowerSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Laser Power"
        self._attr_unique_id = f"{self._device.host}_laser_power"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:laser-pointer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("laser_power")


class SnapmakerLaserFocalLengthSensor(SnapmakerSensorBase):
    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "Laser Focal Length"
        self._attr_unique_id = f"{self._device.host}_laser_focal_length"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
        self._attr_icon = "mdi:laser-pointer"

    @property
    def native_value(self) -> Optional[float]:
        return self._device.data.get("laser_focal_length")


# --- Diagnostic sensor ---


class SnapmakerDiagnosticSensor(SnapmakerSensorBase):
    """Diagnostic sensor exposing the raw API response as extra attributes."""

    def __init__(self, coordinator, device):
        super().__init__(coordinator, device)
        self._attr_name = "API Response"
        self._attr_unique_id = f"{self._device.host}_api_response"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:api"

    @property
    def state(self) -> str:
        return self._device.status

    @property
    def extra_state_attributes(self) -> dict:
        return self._device.raw_api_response
