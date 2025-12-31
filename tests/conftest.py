"""Common fixtures for Snapmaker tests."""

from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_HOST
import pytest


@pytest.fixture
def mock_snapmaker_device():
    """Mock SnapmakerDevice in all import locations."""
    device = MagicMock()
    device.host = "192.168.1.100"
    device.model = "Snapmaker A350"
    device.status = "IDLE"
    device.available = True
    device.dual_extruder = False
    device.data = {
        "ip": "192.168.1.100",
        "model": "Snapmaker A350",
        "status": "IDLE",
        "nozzle_temperature": 25.0,
        "nozzle_target_temperature": 0.0,
        "heated_bed_temperature": 23.0,
        "heated_bed_target_temperature": 0.0,
        "file_name": "N/A",
        "progress": 0,
        "elapsed_time": "00:00:00",
        "remaining_time": "00:00:00",
    }
    device.update.return_value = device.data

    # Patch where SnapmakerDevice is imported and used
    with (
        patch("custom_components.snapmaker.SnapmakerDevice") as mock_init,
        patch("custom_components.snapmaker.config_flow.SnapmakerDevice") as mock_config,
    ):
        mock_init.return_value = device
        mock_config.return_value = device

        # Preserve the discover static method for mock_discovery fixture to patch
        # The discover method will be patched separately by mock_discovery fixture
        mock_config.discover = MagicMock()

        yield mock_init


@pytest.fixture
def mock_discovery():
    """Mock SnapmakerDevice.discover."""
    with patch(
        "custom_components.snapmaker.config_flow.SnapmakerDevice.discover"
    ) as mock:
        mock.return_value = [
            {
                "host": "192.168.1.100",
                "model": "Snapmaker A350",
                "status": "IDLE",
            }
        ]
        yield mock


@pytest.fixture
def mock_socket():
    """Mock socket for UDP communication."""
    with patch("custom_components.snapmaker.snapmaker.socket.socket") as mock:
        socket_instance = MagicMock()
        socket_instance.recvfrom.return_value = (
            b"IP@192.168.1.100|Model:Snapmaker A350|Status:IDLE",
            ("192.168.1.100", 20054),
        )
        mock.return_value = socket_instance
        yield socket_instance


@pytest.fixture
def mock_requests():
    """Mock requests for HTTP communication."""
    with patch("custom_components.snapmaker.snapmaker.requests") as mock:
        # Mock connect response
        connect_response = MagicMock()
        connect_response.text = '{"token": "test-token-123"}'

        # Mock status response
        status_response = MagicMock()
        status_response.text = """{
            "status": "IDLE",
            "nozzleTemperature": 25.0,
            "nozzleTargetTemperature": 0.0,
            "heatedBedTemperature": 23.0,
            "heatedBedTargetTemperature": 0.0,
            "fileName": "test.gcode",
            "progress": 0.5,
            "elapsedTime": 300,
            "remainingTime": 300
        }"""

        mock.post.return_value = connect_response
        mock.get.return_value = status_response
        yield mock


@pytest.fixture
def config_entry_data():
    """Return config entry data."""
    return {CONF_HOST: "192.168.1.100"}


# This fixture is automatically used by pytest-homeassistant-custom-component
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield
