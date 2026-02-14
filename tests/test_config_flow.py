"""Tests for the Snapmaker config flow."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.snapmaker.const import CONF_TOKEN, DOMAIN


@pytest.fixture
def mock_setup_entry():
    """Mock setup entry."""
    with patch(
        "custom_components.snapmaker.async_setup_entry", return_value=True
    ) as mock:
        yield mock


class TestConfigFlow:
    """Test the config flow."""

    async def test_user_flow_success(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test successful user configuration."""
        # Mock generate_token to return a token
        mock_snapmaker_device.return_value.generate_token.return_value = (
            "test-token-123"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Enter IP address - should proceed to authorize step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"

        # Complete authorization - should create entry with token
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Snapmaker Snapmaker A350"
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "test-token-123",
        }

    async def test_user_flow_cannot_connect(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test user configuration with connection error."""
        mock_snapmaker_device.return_value.available = False

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_flow_exception(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test user configuration with exception."""
        mock_snapmaker_device.return_value.update.side_effect = Exception("Test error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    async def test_user_flow_auth_failed(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test user configuration with authorization failure and retry."""
        # Mock generate_token to return None (failure)
        mock_snapmaker_device.return_value.generate_token.return_value = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Enter IP address - should proceed to authorize step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"

        # Try to authorize but it fails
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        # Should show error but stay on authorize form (allows retry)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert result["errors"] == {"base": "auth_failed"}

        # User can retry - this time it succeeds
        mock_snapmaker_device.return_value.generate_token.return_value = (
            "test-token-123"
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        # Should now create entry successfully
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "test-token-123",
        }

    async def test_user_flow_already_configured(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test user configuration when device already configured."""
        # Create existing entry
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Snapmaker",
            data={CONF_HOST: "192.168.1.100"},
            unique_id="192.168.1.100",
        )
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_dhcp_flow_success(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test DHCP discovery flow."""
        # Mock generate_token to return a token
        mock_snapmaker_device.return_value.generate_token.return_value = (
            "test-token-123"
        )

        discovery_info = MagicMock()
        discovery_info.ip = "192.168.1.100"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

        # Should proceed to authorize step
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"

        # Complete authorization
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Snapmaker Snapmaker A350"
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "test-token-123",
        }

    async def test_dhcp_flow_needs_confirmation(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test DHCP discovery that needs user confirmation."""
        mock_snapmaker_device.return_value.available = False

        discovery_info = MagicMock()
        discovery_info.ip = "192.168.1.100"

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

    async def test_confirm_flow_success(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test confirmation flow success."""
        # Mock generate_token to return a token
        mock_snapmaker_device.return_value.generate_token.return_value = (
            "test-token-123"
        )

        # Start with discovery which leads to confirm step
        discovery_info = {
            "host": "192.168.1.100",
            "model": "Snapmaker A350",
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "discovery"},
            data=discovery_info,
        )

        # Should show confirm form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm the setup - should proceed to authorize step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"

        # Complete authorization
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Snapmaker Snapmaker A350"

    async def test_confirm_flow_cannot_connect(
        self, hass, mock_snapmaker_device, mock_setup_entry
    ):
        """Test confirmation flow with connection error."""
        # Start with discovery which leads to confirm step
        discovery_info = {
            "host": "192.168.1.100",
            "model": "Snapmaker A350",
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "discovery"},
            data=discovery_info,
        )

        # Should show confirm form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Now try to confirm but device is unavailable
        mock_snapmaker_device.return_value.available = False

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_discovery_flow(self, hass, mock_snapmaker_device, mock_setup_entry):
        """Test discovery flow."""
        discovery_info = {
            "host": "192.168.1.100",
            "model": "Snapmaker A350",
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "discovery"},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert result["description_placeholders"] == {"host": "192.168.1.100"}

    async def test_discovery_flow_no_data(self, hass, mock_setup_entry):
        """Test discovery flow with no data."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "discovery"},
            data=None,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "not_snapmaker_device"

    async def test_pick_device_flow_success(
        self, hass, mock_discovery, mock_snapmaker_device, mock_setup_entry
    ):
        """Test pick device flow."""
        # Mock generate_token to return a token
        mock_snapmaker_device.return_value.generate_token.return_value = (
            "test-token-123"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        # Navigate to pick_device step and verify its form is shown.
        # Call async_step_pick_device directly on the flow instance to
        # trigger device discovery (no direct path from the user step).
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        result = await flow.async_step_pick_device()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "pick_device"

        # Complete pick_device - should proceed to authorize step
        result = await flow.async_step_pick_device(
            {"device": "192.168.1.100"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "authorize"

        # Complete authorization
        result = await flow.async_step_authorize({})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "test-token-123",
        }

    async def test_pick_device_flow_no_devices(
        self, hass, mock_discovery, mock_setup_entry
    ):
        """Test pick device flow with no devices found."""
        mock_discovery.return_value = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        flow = hass.config_entries.flow._progress[result["flow_id"]]
        result = await flow.async_step_pick_device()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"
