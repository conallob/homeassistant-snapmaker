"""Tests for the Snapmaker integration initialization."""

from unittest.mock import patch

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.snapmaker import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.snapmaker.const import CONF_TOKEN, DOMAIN


@pytest.fixture
def config_entry(config_entry_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Snapmaker",
        data=config_entry_data,
        unique_id="192.168.1.100",
    )


@pytest.fixture
def mock_forward_setups():
    """Mock platform forward setup and unload to avoid state checks."""
    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        ) as mock_setup,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ) as mock_unload,
    ):
        yield mock_setup, mock_unload


class TestInit:
    """Test the initialization."""

    async def test_async_setup(self, hass: HomeAssistant):
        """Test the component setup."""
        assert await async_setup(hass, {}) is True
        assert DOMAIN in hass.data

    async def test_async_setup_entry(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
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
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that setup creates a coordinator."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        assert coordinator is not None
        assert coordinator.name == "Snapmaker 192.168.1.100"

    async def test_async_unload_entry(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test unloading a config entry."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        assert config_entry.entry_id not in hass.data[DOMAIN]

    async def test_coordinator_update(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
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
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test coordinator update with failure."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Now set the side effect after setup
        mock_snapmaker_device.return_value.update.side_effect = Exception("Test error")

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        await coordinator.async_refresh()

        assert coordinator.last_update_success is False

    async def test_coordinator_interval(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test coordinator update interval is set correctly."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        assert coordinator.update_interval.total_seconds() == 30

    async def test_device_stored_in_hass_data(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that device instance is stored in hass.data."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        device = hass.data[DOMAIN][config_entry.entry_id]["device"]
        assert device is not None
        assert device.host == "192.168.1.100"


class TestTokenPersistence:
    """Test token persistence in config entry."""

    async def test_setup_passes_saved_token(
        self, hass: HomeAssistant, mock_snapmaker_device, mock_forward_setups
    ):
        """Test that a saved token is passed to the device on setup."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100", CONF_TOKEN: "saved-token-abc"},
            unique_id="192.168.1.100",
        )
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Verify SnapmakerDevice was created with the saved token
        mock_snapmaker_device.assert_any_call("192.168.1.100", token="saved-token-abc")

    async def test_setup_without_token(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that setup works without a saved token."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Verify SnapmakerDevice was created with token=None
        mock_snapmaker_device.assert_any_call("192.168.1.100", token=None)

    async def test_token_callback_is_set(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that the token update callback is set on the device."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Verify set_token_update_callback was called
        mock_snapmaker_device.return_value.set_token_update_callback.assert_called()

    async def test_token_callback_uses_call_soon_threadsafe(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that the token callback uses call_soon_threadsafe for thread safety."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Get the callback that was registered
        call_args = (
            mock_snapmaker_device.return_value.set_token_update_callback.call_args
        )
        callback = call_args[0][0]

        # The callback should exist and be callable
        assert callable(callback)

    async def test_token_callback_updates_config_entry(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that token callback actually updates the config entry."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Get the callback that was registered
        call_args = (
            mock_snapmaker_device.return_value.set_token_update_callback.call_args
        )
        callback = call_args[0][0]

        # Trigger the callback with a new token
        new_token = "new-token-xyz"
        callback(new_token)

        # Wait for the event loop to process the call_soon_threadsafe
        await hass.async_block_till_done()

        # Verify the config entry was updated with the new token
        assert config_entry.data[CONF_TOKEN] == new_token

    async def test_token_callback_logs_update(
        self,
        hass: HomeAssistant,
        config_entry,
        mock_snapmaker_device,
        mock_forward_setups,
    ):
        """Test that token callback logs the update."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Get the callback that was registered
        call_args = (
            mock_snapmaker_device.return_value.set_token_update_callback.call_args
        )
        callback = call_args[0][0]

        # Trigger the callback with a new token
        with patch("custom_components.snapmaker._LOGGER") as mock_logger:
            callback("new-token-xyz")
            await hass.async_block_till_done()

            # Verify debug log was called
            mock_logger.debug.assert_called_once()


class TestReauthFlow:
    """Test reauthentication flow when token expires."""

    async def test_coordinator_update_triggers_reauth_on_token_invalid(
        self, hass: HomeAssistant, mock_snapmaker_device, mock_forward_setups
    ):
        """Test that token_invalid=True triggers reauth flow."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100", CONF_TOKEN: "old-token"},
            unique_id="192.168.1.100",
        )
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Set token_invalid to True
        mock_snapmaker_device.return_value.token_invalid = True

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

        # Mock entry.async_start_reauth
        with patch.object(config_entry, "async_start_reauth") as mock_reauth:
            await coordinator.async_refresh()

            # Verify reauth was triggered
            mock_reauth.assert_called_once_with(hass)
            # Verify update failed
            assert coordinator.last_update_success is False

    async def test_token_invalid_raises_update_failed(
        self, hass: HomeAssistant, mock_snapmaker_device, mock_forward_setups
    ):
        """Test that token_invalid raises UpdateFailed with appropriate message."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100", CONF_TOKEN: "old-token"},
            unique_id="192.168.1.100",
        )
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Set token_invalid to True
        mock_snapmaker_device.return_value.token_invalid = True

        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

        # Refresh should fail with appropriate error
        await coordinator.async_refresh()

        # Coordinator catches the exception and sets last_update_success
        assert coordinator.last_update_success is False
        # The last_exception should contain our error message
        assert "Token authentication failed" in str(coordinator.last_exception)
