"""Tests for the Snapmaker integration initialization."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.snapmaker import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.snapmaker.const import DOMAIN


@pytest.fixture
def config_entry(config_entry_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Snapmaker",
        data=config_entry_data,
        unique_id="192.168.1.100",
    )


class TestInit:
    """Test the initialization."""

    async def test_async_setup(self, hass: HomeAssistant):
        """Test the component setup."""
        assert await async_setup(hass, {}) is True
        assert DOMAIN in hass.data

    async def test_async_setup_entry(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test setup from a config entry."""
        # Initialize the integration first
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        result = await async_setup_entry(hass, config_entry)

        assert result is True
        assert config_entry.entry_id in hass.data[DOMAIN]
        assert "coordinator" in hass.data[DOMAIN][config_entry.entry_id]
        assert "device" in hass.data[DOMAIN][config_entry.entry_id]

    async def test_async_setup_entry_creates_coordinator(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that setup creates a coordinator."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        assert coordinator is not None
        assert coordinator.name == "Snapmaker 192.168.1.100"

    async def test_async_unload_entry(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test unloading a config entry."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        assert config_entry.entry_id not in hass.data[DOMAIN]

    async def test_coordinator_update(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update method."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        await coordinator.async_refresh()

        assert coordinator.last_update_success is True
        mock_snapmaker_device.return_value.update.assert_called()

    async def test_coordinator_update_failure(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update with failure."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Now set the side effect after setup
        mock_snapmaker_device.return_value.update.side_effect = Exception("Test error")

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

        with pytest.raises(UpdateFailed):
            await coordinator.async_refresh()

        assert coordinator.last_update_success is False

    async def test_coordinator_interval(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update interval is set correctly."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        assert coordinator.update_interval.total_seconds() == 30

    async def test_device_stored_in_hass_data(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that device instance is stored in hass.data."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        device = hass.data[DOMAIN][config_entry.entry_id]["device"]
        assert device is not None
        assert device.host == "192.168.1.100"
