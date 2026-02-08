"""Tests for the Snapmaker integration initialization."""

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
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


class TestTokenPersistence:
    """Test token persistence in config entry."""

    async def test_setup_passes_saved_token(
        self, hass: HomeAssistant, mock_snapmaker_device
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
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that setup works without a saved token."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Verify SnapmakerDevice was created with token=None
        mock_snapmaker_device.assert_any_call("192.168.1.100", token=None)

    async def test_token_callback_is_set(
        self, hass: HomeAssistant, config_entry, mock_snapmaker_device
    ):
        """Test that the token update callback is set on the device."""
        await async_setup(hass, {})
        config_entry.add_to_hass(hass)

        await async_setup_entry(hass, config_entry)

        # Verify set_token_update_callback was called
        mock_snapmaker_device.return_value.set_token_update_callback.assert_called()
