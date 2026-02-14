"""Tests for the Snapmaker binary sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.snapmaker.binary_sensor import (
    SnapmakerAirPurifierBinarySensor,
    SnapmakerDoorOpenBinarySensor,
    SnapmakerEmergencyStopBinarySensor,
    SnapmakerEnclosureBinarySensor,
    SnapmakerFilamentOutBinarySensor,
    SnapmakerRotaryModuleBinarySensor,
    async_setup_entry,
)
from custom_components.snapmaker.const import DOMAIN


@pytest.fixture
def mock_coordinator(mock_snapmaker_device):
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.data = mock_snapmaker_device.return_value.data
    return coordinator


class TestBinarySensorPlatform:
    """Test the binary sensor platform setup."""

    async def test_async_setup_entry(
        self, hass: HomeAssistant, mock_coordinator, mock_snapmaker_device
    ):
        """Test binary sensor platform setup."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

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

        # 6 binary sensors
        assert len(entities) == 6
        assert any(isinstance(e, SnapmakerFilamentOutBinarySensor) for e in entities)
        assert any(isinstance(e, SnapmakerDoorOpenBinarySensor) for e in entities)
        assert any(isinstance(e, SnapmakerEnclosureBinarySensor) for e in entities)
        assert any(isinstance(e, SnapmakerRotaryModuleBinarySensor) for e in entities)
        assert any(isinstance(e, SnapmakerEmergencyStopBinarySensor) for e in entities)
        assert any(isinstance(e, SnapmakerAirPurifierBinarySensor) for e in entities)


class TestBinarySensorEntities:
    """Test individual binary sensor entities."""

    def test_filament_out_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test filament runout binary sensor."""
        sensor = SnapmakerFilamentOutBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Filament Runout"
        assert sensor.unique_id == "192.168.1.100_filament_out"
        assert sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM
        assert sensor.is_on is False

        # Test when filament is out
        mock_snapmaker_device.return_value.data["is_filament_out"] = True
        assert sensor.is_on is True

    def test_door_open_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test door open binary sensor."""
        sensor = SnapmakerDoorOpenBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Door"
        assert sensor.unique_id == "192.168.1.100_door_open"
        assert sensor._attr_device_class == BinarySensorDeviceClass.DOOR
        assert sensor.is_on is False

        # Test when door is open
        mock_snapmaker_device.return_value.data["is_door_open"] = True
        assert sensor.is_on is True

    def test_enclosure_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test enclosure binary sensor."""
        sensor = SnapmakerEnclosureBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Enclosure"
        assert sensor.unique_id == "192.168.1.100_enclosure"
        assert sensor._attr_device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert sensor.is_on is False

        mock_snapmaker_device.return_value.data["has_enclosure"] = True
        assert sensor.is_on is True

    def test_rotary_module_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test rotary module binary sensor."""
        sensor = SnapmakerRotaryModuleBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Rotary Module"
        assert sensor.unique_id == "192.168.1.100_rotary_module"
        assert sensor._attr_device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert sensor.is_on is False

        mock_snapmaker_device.return_value.data["has_rotary_module"] = True
        assert sensor.is_on is True

    def test_emergency_stop_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test emergency stop binary sensor."""
        sensor = SnapmakerEmergencyStopBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Emergency Stop Button"
        assert sensor.unique_id == "192.168.1.100_emergency_stop"
        assert sensor._attr_device_class == BinarySensorDeviceClass.SAFETY
        assert sensor.is_on is False

        mock_snapmaker_device.return_value.data["has_emergency_stop"] = True
        assert sensor.is_on is True

    def test_air_purifier_sensor(self, mock_coordinator, mock_snapmaker_device):
        """Test air purifier binary sensor."""
        sensor = SnapmakerAirPurifierBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor.name == "Air Purifier"
        assert sensor.unique_id == "192.168.1.100_air_purifier"
        assert sensor._attr_device_class == BinarySensorDeviceClass.CONNECTIVITY
        assert sensor.is_on is False

        mock_snapmaker_device.return_value.data["has_air_purifier"] = True
        assert sensor.is_on is True

    def test_binary_sensor_availability(self, mock_coordinator, mock_snapmaker_device):
        """Test binary sensor availability based on coordinator and device."""
        sensor = SnapmakerFilamentOutBinarySensor(
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

    def test_binary_sensor_device_info(self, mock_coordinator, mock_snapmaker_device):
        """Test binary sensor device info."""
        sensor = SnapmakerFilamentOutBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        device_info = sensor.device_info

        assert device_info["identifiers"] == {(DOMAIN, "192.168.1.100")}
        assert device_info["name"] == "Snapmaker Snapmaker A350"
        assert device_info["manufacturer"] == "Snapmaker"
        assert device_info["model"] == "Snapmaker A350"

    def test_binary_sensor_has_entity_name(
        self, mock_coordinator, mock_snapmaker_device
    ):
        """Test that binary sensors have entity name attribute set."""
        sensor = SnapmakerFilamentOutBinarySensor(
            mock_coordinator, mock_snapmaker_device.return_value
        )

        assert sensor._attr_has_entity_name is True
