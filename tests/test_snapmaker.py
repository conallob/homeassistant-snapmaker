"""Tests for the Snapmaker device module."""
import pytest
import socket
from unittest.mock import MagicMock, patch, call
from custom_components.snapmaker.snapmaker import SnapmakerDevice


class TestSnapmakerDevice:
    """Test SnapmakerDevice class."""

    def test_init(self):
        """Test device initialization."""
        device = SnapmakerDevice("192.168.1.100")
        assert device.host == "192.168.1.100"
        assert device.available is False
        assert device.model is None
        assert device.status == "OFFLINE"
        assert device.dual_extruder is False
        assert device.data == {}

    def test_update_offline_device(self, mock_socket):
        """Test update when device is offline."""
        mock_socket.recvfrom.side_effect = socket.timeout()

        device = SnapmakerDevice("192.168.1.100")
        result = device.update()

        assert device.available is False
        assert device.status == "OFFLINE"
        assert result["status"] == "OFFLINE"
        assert result["nozzle_temperature"] == 0
        assert result["file_name"] == "N/A"

    def test_update_online_device(self, mock_socket, mock_requests):
        """Test update when device is online."""
        device = SnapmakerDevice("192.168.1.100")
        result = device.update()

        assert device.available is True
        assert device.model == "Snapmaker A350"
        assert device.status == "IDLE"
        assert "nozzle_temperature" in result
        assert "heated_bed_temperature" in result

    def test_check_online_success(self, mock_socket):
        """Test successful device discovery."""
        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        assert device.available is True
        assert device.model == "Snapmaker A350"
        assert device.status == "IDLE"
        assert device.data["ip"] == "192.168.1.100"

        # Verify broadcast message was sent
        mock_socket.sendto.assert_called()
        call_args = mock_socket.sendto.call_args[0]
        assert call_args[0] == b"discover"
        assert call_args[1] == ("255.255.255.255", 20054)

    def test_check_online_filters_wrong_device(self, mock_socket):
        """Test that _check_online filters responses from wrong devices."""
        # First response is from a different device
        mock_socket.recvfrom.side_effect = [
            (
                b"IP@192.168.1.99|Model:Snapmaker A150|Status:IDLE",
                ("192.168.1.99", 20054),
            ),
            (
                b"IP@192.168.1.100|Model:Snapmaker A350|Status:IDLE",
                ("192.168.1.100", 20054),
            ),
        ]

        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        assert device.available is True
        assert device.model == "Snapmaker A350"
        assert device.data["ip"] == "192.168.1.100"

    def test_check_online_timeout(self, mock_socket):
        """Test device discovery timeout."""
        mock_socket.recvfrom.side_effect = socket.timeout()

        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        assert device.available is False
        assert device.status == "OFFLINE"
        # Should retry MAX_RETRIES times
        assert mock_socket.sendto.call_count == 5

    def test_get_token_success(self, mock_requests):
        """Test successful token retrieval."""
        device = SnapmakerDevice("192.168.1.100")
        token = device._get_token()

        assert token == "test-token-123"
        assert mock_requests.post.call_count == 2

    def test_get_token_failure(self, mock_requests):
        """Test token retrieval failure."""
        mock_requests.post.return_value.text = '{"error": "Failed"}'

        device = SnapmakerDevice("192.168.1.100")
        token = device._get_token()

        assert token is None

    def test_get_token_no_token_in_response(self, mock_requests):
        """Test token retrieval when no token in response."""
        mock_requests.post.return_value.text = '{}'

        device = SnapmakerDevice("192.168.1.100")
        token = device._get_token()

        assert token is None

    def test_get_status_single_extruder(self, mock_requests):
        """Test status retrieval for single extruder device."""
        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._status = "IDLE"
        device._get_status()

        assert device.dual_extruder is False
        assert device.data["nozzle_temperature"] == 25.0
        assert device.data["nozzle_target_temperature"] == 0.0
        assert device.data["heated_bed_temperature"] == 23.0
        assert device.data["file_name"] == "test.gcode"
        assert device.data["progress"] == 50.0
        assert device.data["elapsed_time"] == "0:05:00"
        assert device.data["remaining_time"] == "0:05:00"

    def test_get_status_dual_extruder(self, mock_requests):
        """Test status retrieval for dual extruder device."""
        mock_requests.get.return_value.text = """{
            "status": "RUNNING",
            "nozzle1Temperature": 200.0,
            "nozzle1TargetTemperature": 210.0,
            "nozzle2Temperature": 195.0,
            "nozzle2TargetTemperature": 200.0,
            "heatedBedTemperature": 60.0,
            "heatedBedTargetTemperature": 65.0,
            "fileName": "dual_print.gcode",
            "progress": 0.75,
            "elapsedTime": 1800,
            "remainingTime": 600
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._status = "RUNNING"
        device._get_status()

        assert device.dual_extruder is True
        assert device.data["nozzle1_temperature"] == 200.0
        assert device.data["nozzle1_target_temperature"] == 210.0
        assert device.data["nozzle2_temperature"] == 195.0
        assert device.data["nozzle2_target_temperature"] == 200.0
        assert device.data["progress"] == 75.0

    def test_get_status_empty_response(self, mock_requests):
        """Test status retrieval with empty response."""
        mock_requests.get.return_value.text = ""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.available is False
        assert device.status == "OFFLINE"

    def test_get_status_invalid_json(self, mock_requests):
        """Test status retrieval with invalid JSON."""
        mock_requests.get.return_value.text = "invalid json {"

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.available is False
        assert device.status == "OFFLINE"

    def test_get_status_http_error(self, mock_requests):
        """Test status retrieval with HTTP error."""
        mock_requests.get.return_value.raise_for_status.side_effect = Exception(
            "HTTP Error"
        )

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.available is False
        assert device.status == "OFFLINE"

    def test_discover_devices(self, mock_socket):
        """Test static discover method."""
        mock_socket.recvfrom.side_effect = [
            (
                b"IP@192.168.1.100|Model:Snapmaker A350|Status:IDLE",
                ("192.168.1.100", 20054),
            ),
            (
                b"IP@192.168.1.101|Model:Snapmaker A250|Status:RUNNING",
                ("192.168.1.101", 20054),
            ),
            socket.timeout(),
        ]

        devices = SnapmakerDevice.discover()

        assert len(devices) == 2
        assert devices[0]["host"] == "192.168.1.100"
        assert devices[0]["model"] == "Snapmaker A350"
        assert devices[0]["status"] == "IDLE"
        assert devices[1]["host"] == "192.168.1.101"
        assert devices[1]["model"] == "Snapmaker A250"
        assert devices[1]["status"] == "RUNNING"

    def test_discover_no_devices(self, mock_socket):
        """Test discover when no devices respond."""
        mock_socket.recvfrom.side_effect = socket.timeout()

        devices = SnapmakerDevice.discover()

        assert len(devices) == 0

    def test_discover_exception(self):
        """Test discover with exception."""
        with patch("custom_components.snapmaker.snapmaker.socket.socket") as mock:
            mock.side_effect = Exception("Socket error")

            devices = SnapmakerDevice.discover()

            assert len(devices) == 0

    def test_set_offline(self):
        """Test _set_offline method."""
        device = SnapmakerDevice("192.168.1.100")
        device._model = "Snapmaker A350"
        device._set_offline()

        assert device.available is False
        assert device.status == "OFFLINE"
        assert device.data["status"] == "OFFLINE"
        assert device.data["ip"] == "192.168.1.100"
        assert device.data["model"] == "Snapmaker A350"
        assert device.data["nozzle_temperature"] == 0
        assert device.data["file_name"] == "N/A"

    def test_check_online_malformed_response(self, mock_socket):
        """Test _check_online with malformed response."""
        mock_socket.recvfrom.side_effect = [
            (b"INVALID_RESPONSE", ("192.168.1.100", 20054)),
            socket.timeout(),
        ]

        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        # Should mark as offline due to malformed response
        assert device.available is False
        assert device.status == "OFFLINE"

    def test_check_online_invalid_utf8(self, mock_socket):
        """Test _check_online with invalid UTF-8 bytes."""
        mock_socket.recvfrom.side_effect = [
            (b"\xff\xfe\x00\x00", ("192.168.1.100", 20054)),
            socket.timeout(),
        ]

        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        # Should handle decode error gracefully
        assert device.available is False
        assert device.status == "OFFLINE"

    def test_discover_malformed_response(self, mock_socket):
        """Test discover with malformed response."""
        mock_socket.recvfrom.side_effect = [
            (b"IP@192.168.1.100|Model:Snapmaker A350|Status:IDLE", ("192.168.1.100", 20054)),
            (b"INVALID", ("192.168.1.101", 20054)),
            socket.timeout(),
        ]

        devices = SnapmakerDevice.discover()

        # Should only include valid device
        assert len(devices) == 1
        assert devices[0]["host"] == "192.168.1.100"

    def test_check_online_socket_closed_on_exception(self):
        """Test that socket is closed even when exception occurs."""
        with patch("custom_components.snapmaker.snapmaker.socket.socket") as mock_socket_class:
            socket_instance = MagicMock()
            socket_instance.sendto.side_effect = Exception("Send error")
            mock_socket_class.return_value = socket_instance

            device = SnapmakerDevice("192.168.1.100")
            device._check_online()

            # Socket should be closed even though exception occurred
            socket_instance.close.assert_called_once()
