"""Tests for the Snapmaker sensor platform."""

from unittest.mock import MagicMock

from homeassistant.const import CONF_HOST, PERCENTAGE, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.snapmaker.const import (
    DOMAIN,
    TOOLHEAD_MAP,
    TOOLHEAD_TYPE_CNC,
    TOOLHEAD_TYPE_DUAL_EXTRUDER,
    TOOLHEAD_TYPE_EXTRUDER,
    TOOLHEAD_TYPE_LASER,
)
from custom_components.snapmaker.sensor import (
    SnapmakerBedTargetTempSensor,
    SnapmakerBedTempSensor,
    SnapmakerCurrentLineSensor,
    SnapmakerDiagnosticSensor,
    SnapmakerElapsedTimeSensor,
    SnapmakerEstimatedTimeSensor,
    SnapmakerFileNameSensor,
    SnapmakerHomingSensor,
    SnapmakerLaserFocalLengthSensor,
    SnapmakerLaserPowerSensor,
    SnapmakerNozzle1TempSensor,
    SnapmakerNozzle2TempSensor,
    SnapmakerNozzleTargetTempSensor,
    SnapmakerNozzleTempSensor,
    SnapmakerPositionXSensor,
    SnapmakerPositionYSensor,
    SnapmakerPositionZSensor,
    SnapmakerProgressSensor,
    SnapmakerRemainingTimeSensor,
    SnapmakerSpindleSpeedSensor,
    SnapmakerStatusSensor,
    SnapmakerToolHeadSensor,
    SnapmakerTotalLinesSensor,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator(mock_snapmaker_device):
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.data = mock_snapmaker_device.return_value.data
    return coordinator


@pytest.fixture
def config_entry(config_entry_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Snapmaker",
        data=config_entry_data,
        unique_id="192.168.1.100",
    )


class TestSensorPlatform:
    """Test the sensor platform setup."""

    async def test_async_setup_entry_single_extruder(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test sensor platform setup for single extruder."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        mock_snapmaker_device.return_value.dual_extruder = False
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "device": mock_snapmaker_device.return_value,
            }
        }

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(hass, config_entry, mock_add_entities)

        # 16 common sensors + 2 single nozzle sensors = 18
        # (CNC/Laser sensors are only added for matching toolhead types)
        assert len(entities) == 18
        assert any(isinstance(e, SnapmakerStatusSensor) for e in entities)
        assert any(isinstance(e, SnapmakerNozzleTempSensor) for e in entities)
        assert any(isinstance(e, SnapmakerBedTempSensor) for e in entities)
        assert any(isinstance(e, SnapmakerFileNameSensor) for e in entities)
        assert any(isinstance(e, SnapmakerProgressSensor) for e in entities)
        assert any(isinstance(e, SnapmakerToolHeadSensor) for e in entities)
        assert any(isinstance(e, SnapmakerPositionXSensor) for e in entities)
        assert any(isinstance(e, SnapmakerTotalLinesSensor) for e in entities)
        assert any(isinstance(e, SnapmakerDiagnosticSensor) for e in entities)
        # Verify no CNC/Laser sensors for Extruder toolhead
        assert not any(isinstance(e, SnapmakerSpindleSpeedSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserPowerSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserFocalLengthSensor) for e in entities)

    async def test_async_setup_entry_dual_extruder(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test sensor platform setup for dual extruder."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        mock_snapmaker_device.return_value.dual_extruder = True
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "device": mock_snapmaker_device.return_value,
            }
        }

        entities = []

        def mock_add_entities(new_entities):
            entities.extend(new_entities)

        await async_setup_entry(hass, config_entry, mock_add_entities)

        # 16 common sensors + 4 dual nozzle sensors = 20
        assert len(entities) == 20
        assert any(isinstance(e, SnapmakerNozzle1TempSensor) for e in entities)
        assert any(isinstance(e, SnapmakerNozzle2TempSensor) for e in entities)

    async def test_async_setup_entry_cnc_toolhead(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test sensor platform setup for CNC toolhead."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        mock_snapmaker_device.return_value.dual_extruder = False
        mock_snapmaker_device.return_value.toolhead_type = "CNC"
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "device": mock_snapmaker_device.return_value,
            }
        }

        entities = []
        await async_setup_entry(hass, config_entry, entities.extend)

        # 16 common + 1 spindle + 2 nozzle = 19
        assert len(entities) == 19
        assert any(isinstance(e, SnapmakerSpindleSpeedSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserPowerSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserFocalLengthSensor) for e in entities)

    async def test_async_setup_entry_laser_toolhead(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test sensor platform setup for Laser toolhead."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        mock_snapmaker_device.return_value.dual_extruder = False
        mock_snapmaker_device.return_value.toolhead_type = "Laser"
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "device": mock_snapmaker_device.return_value,
            }
        }

        entities = []
        await async_setup_entry(hass, config_entry, entities.extend)

        # 16 common + 2 laser + 2 nozzle = 20
        assert len(entities) == 20
        assert not any(isinstance(e, SnapmakerSpindleSpeedSensor) for e in entities)
        assert any(isinstance(e, SnapmakerLaserPowerSensor) for e in entities)
        assert any(isinstance(e, SnapmakerLaserFocalLengthSensor) for e in entities)

    async def test_async_setup_entry_unknown_toolhead(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test sensor platform setup with unknown/None toolhead type."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        mock_snapmaker_device.return_value.dual_extruder = False
        mock_snapmaker_device.return_value.toolhead_type = None
        hass.data[DOMAIN] = {
            config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "device": mock_snapmaker_device.return_value,
            }
        }

        entities = []
        await async_setup_entry(hass, config_entry, entities.extend)

        # 16 common + 0 toolhead-specific + 2 nozzle = 18
        assert len(entities) == 18
        assert not any(isinstance(e, SnapmakerSpindleSpeedSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserPowerSensor) for e in entities)
        assert not any(isinstance(e, SnapmakerLaserFocalLengthSensor) for e in entities)

    async def test_toolhead_sensors_diagnostic_category(
        self, mock_coordinator, mock_snapmaker_device
    ):
        """Test that CNC/Laser sensors have diagnostic entity category."""
        from homeassistant.const import EntityCategory

        device = mock_snapmaker_device.return_value

        spindle = SnapmakerSpindleSpeedSensor(mock_coordinator, device)
        assert spindle._attr_entity_category == EntityCategory.DIAGNOSTIC

        laser_power = SnapmakerLaserPowerSensor(mock_coordinator, device)
        assert laser_power._attr_entity_category == EntityCategory.DIAGNOSTIC

        laser_focal = SnapmakerLaserFocalLengthSensor(mock_coordinator, device)
        assert laser_focal._attr_entity_category == EntityCategory.DIAGNOSTIC


class TestToolheadConstants:
    """Test that toolhead type constants are consistent with TOOLHEAD_MAP."""

    def test_toolhead_type_constants_in_map(self):
        """Ensure toolhead type constants match values in TOOLHEAD_MAP."""
        map_values = set(TOOLHEAD_MAP.values())
        assert TOOLHEAD_TYPE_EXTRUDER in map_values
        assert TOOLHEAD_TYPE_DUAL_EXTRUDER in map_values
        assert TOOLHEAD_TYPE_CNC in map_values
        assert TOOLHEAD_TYPE_LASER in map_values


class TestSensorEntities:
    """Test individual sensor entities."""

    def test_status_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test status sensor."""
        sensor = SnapmakerStatusSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Status"
        assert sensor.unique_id == "192.168.1.100_status"
        assert sensor.icon == "mdi:printer-3d"
        assert sensor.state == "IDLE"
        assert sensor.available is True

    def test_nozzle_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test nozzle temperature sensor."""
        sensor = SnapmakerNozzleTempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Nozzle Temperature"
        assert sensor.unique_id == "192.168.1.100_nozzle_temp"
        assert sensor._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert sensor.native_value == 25.0
        assert sensor._attr_icon == "mdi:thermometer"

    def test_nozzle_target_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test nozzle target temperature sensor."""
        sensor = SnapmakerNozzleTargetTempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Nozzle Target Temperature"
        assert sensor.unique_id == "192.168.1.100_nozzle_target_temp"
        assert sensor.native_value == 0.0

    def test_bed_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test bed temperature sensor."""
        sensor = SnapmakerBedTempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Bed Temperature"
        assert sensor.unique_id == "192.168.1.100_bed_temp"
        assert sensor._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS
        assert sensor.native_value == 23.0

    def test_bed_target_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test bed target temperature sensor."""
        sensor = SnapmakerBedTargetTempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Bed Target Temperature"
        assert sensor.unique_id == "192.168.1.100_bed_target_temp"
        assert sensor.native_value == 0.0

    def test_file_name_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test file name sensor."""
        sensor = SnapmakerFileNameSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "File Name"
        assert sensor.unique_id == "192.168.1.100_file_name"
        assert sensor.state == "N/A"
        assert sensor.icon == "mdi:file-document"

    def test_progress_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test progress sensor."""
        sensor = SnapmakerProgressSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Progress"
        assert sensor.unique_id == "192.168.1.100_progress"
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE
        assert sensor.native_value == 0
        assert sensor._attr_icon == "mdi:progress-check"

    def test_elapsed_time_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test elapsed time sensor."""
        sensor = SnapmakerElapsedTimeSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Elapsed Time"
        assert sensor.unique_id == "192.168.1.100_elapsed_time"
        assert sensor.state == "00:00:00"
        assert sensor.icon == "mdi:clock-outline"

    def test_remaining_time_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test remaining time sensor."""
        sensor = SnapmakerRemainingTimeSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Remaining Time"
        assert sensor.unique_id == "192.168.1.100_remaining_time"
        assert sensor.state == "00:00:00"
        assert sensor.icon == "mdi:clock-end"

    def test_estimated_time_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test estimated time sensor."""
        sensor = SnapmakerEstimatedTimeSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Estimated Time"
        assert sensor.unique_id == "192.168.1.100_estimated_time"
        assert sensor.state == "00:00:00"
        assert sensor.icon == "mdi:clock-start"

    def test_tool_head_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test tool head sensor."""
        sensor = SnapmakerToolHeadSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Tool Head"
        assert sensor.unique_id == "192.168.1.100_tool_head"
        assert sensor.state == "Extruder"
        assert sensor.icon == "mdi:toolbox"

    def test_position_x_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test position X sensor."""
        sensor = SnapmakerPositionXSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Position X"
        assert sensor.unique_id == "192.168.1.100_position_x"
        assert sensor._attr_native_unit_of_measurement == UnitOfLength.MILLIMETERS
        assert sensor.native_value == 0
        assert sensor.icon == "mdi:axis-x-arrow"

    def test_position_y_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test position Y sensor."""
        sensor = SnapmakerPositionYSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Position Y"
        assert sensor.unique_id == "192.168.1.100_position_y"
        assert sensor._attr_native_unit_of_measurement == UnitOfLength.MILLIMETERS
        assert sensor.native_value == 0
        assert sensor.icon == "mdi:axis-y-arrow"

    def test_position_z_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test position Z sensor."""
        sensor = SnapmakerPositionZSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Position Z"
        assert sensor.unique_id == "192.168.1.100_position_z"
        assert sensor._attr_native_unit_of_measurement == UnitOfLength.MILLIMETERS
        assert sensor.native_value == 0
        assert sensor.icon == "mdi:axis-z-arrow"

    def test_homing_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test homing sensor."""
        sensor = SnapmakerHomingSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Homing"
        assert sensor.unique_id == "192.168.1.100_homing"
        assert sensor.state == "N/A"
        assert sensor.icon == "mdi:home-import-outline"

    def test_total_lines_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test total G-code lines sensor."""
        sensor = SnapmakerTotalLinesSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Total G-code Lines"
        assert sensor.unique_id == "192.168.1.100_total_lines"
        assert sensor.native_value == 0
        assert sensor.icon == "mdi:code-braces"

    def test_current_line_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test current G-code line sensor."""
        sensor = SnapmakerCurrentLineSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Current G-code Line"
        assert sensor.unique_id == "192.168.1.100_current_line"
        assert sensor.native_value == 0
        assert sensor.icon == "mdi:code-braces"

    def test_diagnostic_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test diagnostic sensor with raw API response."""
        sensor = SnapmakerDiagnosticSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "API Response"
        assert sensor.unique_id == "192.168.1.100_api_response"
        assert sensor.state == "IDLE"
        assert sensor.icon == "mdi:api"

        # Check extra attributes contain the raw API response
        attrs = sensor.extra_state_attributes
        assert attrs["status"] == "IDLE"
        assert attrs["nozzleTemperature"] == 25.0

    def test_nozzle1_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test nozzle 1 temperature sensor for dual extruder."""
        mock_snapmaker_device.return_value.data["nozzle1_temperature"] = 200.0

        sensor = SnapmakerNozzle1TempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Nozzle 1 Temperature"
        assert sensor.unique_id == "192.168.1.100_nozzle1_temp"
        assert sensor.native_value == 200.0

    def test_nozzle2_temp_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test nozzle 2 temperature sensor for dual extruder."""
        mock_snapmaker_device.return_value.data["nozzle2_temperature"] = 195.0

        sensor = SnapmakerNozzle2TempSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Nozzle 2 Temperature"
        assert sensor.unique_id == "192.168.1.100_nozzle2_temp"
        assert sensor.native_value == 195.0

    def test_spindle_speed_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test CNC spindle speed sensor."""
        mock_snapmaker_device.return_value.data["spindle_speed"] = 12000

        sensor = SnapmakerSpindleSpeedSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Spindle Speed"
        assert sensor.unique_id == "192.168.1.100_spindle_speed"
        assert sensor.native_value == 12000
        assert sensor._attr_native_unit_of_measurement == "RPM"
        assert sensor.icon == "mdi:rotate-right"

    def test_laser_power_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test laser power sensor."""
        mock_snapmaker_device.return_value.data["laser_power"] = 85

        sensor = SnapmakerLaserPowerSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Laser Power"
        assert sensor.unique_id == "192.168.1.100_laser_power"
        assert sensor.native_value == 85
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE
        assert sensor.icon == "mdi:laser-pointer"

    def test_laser_focal_length_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test laser focal length sensor."""
        mock_snapmaker_device.return_value.data["laser_focal_length"] = 50.0

        sensor = SnapmakerLaserFocalLengthSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Laser Focal Length"
        assert sensor.unique_id == "192.168.1.100_laser_focal_length"
        assert sensor.native_value == 50.0
        assert sensor._attr_native_unit_of_measurement == UnitOfLength.MILLIMETERS
        assert sensor.icon == "mdi:laser-pointer"

    def test_cnc_laser_sensors_none_when_not_available(
        self, mock_coordinator, mock_snapmaker_device
    ):
        """Test CNC/laser sensors return None when data not available."""
        sensor = SnapmakerSpindleSpeedSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )
        assert sensor.native_value is None

        sensor = SnapmakerLaserPowerSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )
        assert sensor.native_value is None

        sensor = SnapmakerLaserFocalLengthSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )
        assert sensor.native_value is None

    def test_sensor_availability(self, mock_coordinator, mock_snapmaker_device):
        """Test sensor availability based on coordinator and device."""
        sensor = SnapmakerStatusSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        # Both coordinator and device available
        mock_coordinator.last_update_success = True
        mock_snapmaker_device.return_value.available = True
        assert sensor.available is True

        # Coordinator failed
        mock_coordinator.last_update_success = False
        assert sensor.available is False

        # Device unavailable
        mock_coordinator.last_update_success = True
        mock_snapmaker_device.return_value.available = False
        assert sensor.available is False

    def test_sensor_device_info(self, mock_coordinator, mock_snapmaker_device):
        """Test sensor device info."""
        sensor = SnapmakerStatusSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "192.168.1.100")}
        assert device_info["name"] == "Snapmaker Snapmaker A350"
        assert device_info["manufacturer"] == "Snapmaker"
        assert device_info["model"] == "Snapmaker A350"

    def test_sensor_has_entity_name(self, mock_coordinator, mock_snapmaker_device):
        """Test that sensors have entity name attribute set."""
        sensor = SnapmakerStatusSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor._attr_has_entity_name is True

    def test_sensor_with_missing_data(self, mock_coordinator, mock_snapmaker_device):
        """Test sensor behavior with missing data keys."""
        # Remove some keys from data
        mock_snapmaker_device.return_value.data = {
            "ip": "192.168.1.100",
            "model": "Snapmaker A350",
            "status": "IDLE",
        }

        sensor = SnapmakerProgressSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        # Should return None when key is missing
        assert sensor.native_value is None

        file_sensor = SnapmakerFileNameSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )
        assert file_sensor.state == "N/A"

        tool_sensor = SnapmakerToolHeadSensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )
        assert tool_sensor.state == "N/A"
