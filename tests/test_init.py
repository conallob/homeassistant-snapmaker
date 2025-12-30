"""Tests for the Snapmaker integration initialization."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from custom_components.snapmaker import async_setup, async_setup_entry, async_unload_entry
from custom_components.snapmaker.const import DOMAIN


@pytest.fixture
def config_entry(config_entry_data):
    """Create a mock config entry."""
    entry = ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="Snapmaker",
        data=config_entry_data,
        source="user",
        unique_id="192.168.1.100",
    )
    return entry


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
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ) as mock_forward:
            result = await async_setup_entry(hass, config_entry)

            assert result is True
            assert config_entry.entry_id in hass.data[DOMAIN]
            assert "coordinator" in hass.data[DOMAIN][config_entry.entry_id]
            assert "device" in hass.data[DOMAIN][config_entry.entry_id]

    async def test_async_setup_entry_creates_coordinator(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that setup creates a coordinator."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

            coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
            assert coordinator is not None
            assert coordinator.name == "Snapmaker 192.168.1.100"

    async def test_async_unload_entry(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test unloading a config entry."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

        with patch(
            "custom_components.snapmaker.async_unload_platforms",
            return_value=True,
        ) as mock_unload:
            result = await async_unload_entry(hass, config_entry)

            assert result is True
            assert config_entry.entry_id not in hass.data[DOMAIN]
            mock_unload.assert_called_once()

    async def test_coordinator_update(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update method."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

            coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
            await coordinator.async_refresh()

            assert coordinator.last_update_success is True
            mock_snapmaker_device.return_value.update.assert_called()

    async def test_coordinator_update_failure(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update with failure."""
        mock_snapmaker_device.return_value.update.side_effect = Exception("Test error")
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

            coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

            with pytest.raises(UpdateFailed):
                await coordinator.async_refresh()

            assert coordinator.last_update_success is False

    async def test_coordinator_interval(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test coordinator update interval is set correctly."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

            coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
            assert coordinator.update_interval.total_seconds() == 30

    async def test_device_stored_in_hass_data(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that device instance is stored in hass.data."""
        config_entry.add_to_hass(hass)

        with patch(
            "custom_components.snapmaker.async_forward_entry_setups",
            return_value=True,
        ):
            await async_setup_entry(hass, config_entry)

            device = hass.data[DOMAIN][config_entry.entry_id]["device"]
            assert device is not None
            assert device.host == "192.168.1.100"
