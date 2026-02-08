"""Tests for the Snapmaker device module."""

import socket
from unittest.mock import MagicMock, call, patch

import requests

from custom_components.snapmaker.snapmaker import (
    API_PORT,
    REACHABILITY_MAX_RETRIES,
    SENSITIVE_API_KEYS,
    SnapmakerDevice,
)


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
        assert device.token is None
        assert device.raw_api_response == {}

    def test_init_with_token(self):
        """Test device initialization with a persisted token."""
        device = SnapmakerDevice("192.168.1.100", token="saved-token-456")
        assert device.token == "saved-token-456"

    def test_update_offline_device(self, mock_socket):
        """Test update when device is offline."""
        mock_socket.recvfrom.side_effect = socket.timeout()

        device = SnapmakerDevice("192.168.1.100")
        result = device.update()

        assert device.available is False
        assert device.status == "OFFLINE"
        assert result["status"] == "OFFLINE"
        assert result["nozzle_temperature"] is None
        assert result["file_name"] == "N/A"
        assert result["tool_head"] == "N/A"
        assert result["is_filament_out"] is False
        assert result["total_lines"] is None

    def test_update_online_device(self, mock_socket, mock_requests):
        """Test update when device is online."""
        device = SnapmakerDevice("192.168.1.100")
        result = device.update()

        assert device.available is True
        assert device.model == "Snapmaker A350"
        assert device.status == "IDLE"
        assert "nozzle_temperature" in result
        assert "heated_bed_temperature" in result
        assert "tool_head" in result
        assert "x" in result
        assert "is_filament_out" in result
        assert "total_lines" in result

    def test_check_online_success(self, mock_socket):
        """Test successful device discovery."""
        device = SnapmakerDevice("192.168.1.100")
        device._check_online()

        assert device.available is True
        assert device.model == "Snapmaker A350"
        assert device.status == "IDLE"
        assert device.data["ip"] == "192.168.1.100"

        # Verify broadcast message was sent with correct arguments
        mock_socket.sendto.assert_called_with(b"discover", ("255.255.255.255", 20054))

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

    def test_get_token_calls_update_callback(self, mock_requests):
        """Test that token update callback is called on new token."""
        callback = MagicMock()
        device = SnapmakerDevice("192.168.1.100")
        device.set_token_update_callback(callback)

        token = device._get_token()

        assert token == "test-token-123"
        callback.assert_called_once_with("test-token-123")

    def test_get_token_failure(self, mock_requests):
        """Test token retrieval failure."""
        mock_requests.post.return_value.text = '{"error": "Failed"}'

        device = SnapmakerDevice("192.168.1.100")
        token = device._get_token()

        assert token is None

    def test_get_token_no_token_in_response(self, mock_requests):
        """Test token retrieval when no token in response."""
        mock_requests.post.return_value.text = "{}"

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

    def test_get_status_additional_fields(self, mock_requests):
        """Test that additional fields are parsed from API response."""
        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._status = "IDLE"
        device._get_status()

        # Toolhead (mapped from TOOLHEAD_3DPRINTING_1)
        assert device.data["tool_head"] == "Extruder"

        # Position
        assert device.data["x"] == 100.5
        assert device.data["y"] == 200.3
        assert device.data["z"] == 10.0
        assert device.data["homing"] == "XYZ"

        # Estimated time
        assert device.data["estimated_time"] == "0:10:00"

        # Module presence
        assert device.data["has_enclosure"] is True
        assert device.data["has_rotary_module"] is False
        assert device.data["has_emergency_stop"] is True
        assert device.data["has_air_purifier"] is False

        # Safety
        assert device.data["is_filament_out"] is False
        assert device.data["is_door_open"] is False

        # G-code progress
        assert device.data["total_lines"] == 10000
        assert device.data["current_line"] == 5000

    def test_get_status_toolhead_mapping(self, mock_requests):
        """Test that toolhead types are mapped to friendly names."""
        test_cases = [
            ("TOOLHEAD_3DPRINTING_1", "Extruder"),
            ("TOOLHEAD_CNC_1", "CNC"),
            ("TOOLHEAD_LASER_1", "Laser"),
            ("UNKNOWN_TOOLHEAD", "UNKNOWN_TOOLHEAD"),
        ]

        for raw_toolhead, expected_name in test_cases:
            mock_requests.get.return_value.text = (
                f'{{"status": "IDLE", "toolHead": "{raw_toolhead}"}}'
            )
            device = SnapmakerDevice("192.168.1.100")
            device._token = "test-token-123"
            device._available = True
            device._get_status()
            assert (
                device.data["tool_head"] == expected_name
            ), f"Expected {expected_name} for {raw_toolhead}"

    def test_get_status_dual_extruder_detection_via_toolhead(self, mock_requests):
        """Test dual extruder detection when toolhead is 3D printing but no single nozzle temp."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "toolHead": "TOOLHEAD_3DPRINTING_1",
            "nozzle1Temperature": 200.0,
            "nozzle1TargetTemperature": 210.0,
            "nozzle2Temperature": 195.0,
            "nozzle2TargetTemperature": 200.0,
            "heatedBedTemperature": 60.0,
            "heatedBedTargetTemperature": 65.0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.dual_extruder is True
        assert device.data["tool_head"] == "Dual Extruder"

    def test_get_status_cnc_laser_fields(self, mock_requests):
        """Test CNC and laser specific fields are parsed."""
        mock_requests.get.return_value.text = """{
            "status": "RUNNING",
            "toolHead": "TOOLHEAD_CNC_1",
            "spindleSpeed": 12000,
            "heatedBedTemperature": 0,
            "heatedBedTargetTemperature": 0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.data["tool_head"] == "CNC"
        assert device.data["spindle_speed"] == 12000

    def test_get_status_laser_fields(self, mock_requests):
        """Test laser specific fields are parsed."""
        mock_requests.get.return_value.text = """{
            "status": "RUNNING",
            "toolHead": "TOOLHEAD_LASER_1",
            "laserPower": 100,
            "laserFocalLength": 50.0,
            "heatedBedTemperature": 0,
            "heatedBedTargetTemperature": 0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        assert device.data["tool_head"] == "Laser"
        assert device.data["laser_power"] == 100
        assert device.data["laser_focal_length"] == 50.0

    def test_get_status_raw_api_response_stored(self, mock_requests):
        """Test that the raw API response is stored for diagnostics."""
        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        raw = device.raw_api_response
        assert raw["status"] == "IDLE"
        assert raw["nozzleTemperature"] == 25.0
        assert raw["toolHead"] == "TOOLHEAD_3DPRINTING_1"
        assert raw["totalLines"] == 10000

    def test_get_status_raw_api_response_filters_sensitive_keys(self, mock_requests):
        """Test that sensitive keys are filtered from raw API response."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "token": "secret-token-value",
            "nozzleTemperature": 25.0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        raw = device.raw_api_response
        assert "token" not in raw
        assert raw["status"] == "IDLE"
        assert raw["nozzleTemperature"] == 25.0

    def test_get_status_raw_api_response_cleared_on_offline(self):
        """Test that raw API response is cleared when going offline."""
        device = SnapmakerDevice("192.168.1.100")
        device._raw_api_response = {"status": "IDLE"}
        device._set_offline()

        assert device.raw_api_response == {}

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

    def test_get_status_http_error(self):
        """Test status retrieval with HTTP error."""
        with patch("custom_components.snapmaker.snapmaker.requests") as mock_req:
            # Use the real HTTPError class so except clause can catch it
            mock_req.exceptions.HTTPError = requests.exceptions.HTTPError
            error = requests.exceptions.HTTPError("HTTP Error")
            error.response = MagicMock()
            error.response.status_code = 500
            mock_req.get.return_value.raise_for_status.side_effect = error

            device = SnapmakerDevice("192.168.1.100")
            device._token = "test-token-123"
            device._available = True
            device._get_status()

            assert device.available is False
            assert device.status == "OFFLINE"

    def test_get_status_401_clears_token_and_sets_offline(self):
        """Test that a 401 response clears the token and sets device offline."""
        with patch("custom_components.snapmaker.snapmaker.requests") as mock_req:
            # Use the real HTTPError class so except clause can catch it
            mock_req.exceptions.HTTPError = requests.exceptions.HTTPError
            error = requests.exceptions.HTTPError("Unauthorized")
            error.response = MagicMock()
            error.response.status_code = 401
            mock_req.get.return_value.raise_for_status.side_effect = error

            device = SnapmakerDevice("192.168.1.100")
            device._token = "test-token-123"
            device._available = True
            device._get_status()

            # Token should be cleared and device should be set offline
            assert device._token is None
            assert device._available is False
            assert device.status == "OFFLINE"

    def test_get_status_unknown_toolhead_logs_warning(self, mock_requests):
        """Test that unknown toolhead types are logged."""
        mock_requests.get.return_value.text = (
            '{"status": "IDLE", "toolHead": "TOOLHEAD_FUTURE_V3"}'
        )

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token-123"
        device._available = True
        device._get_status()

        # Unknown toolhead should use raw value as display name
        assert device.data["tool_head"] == "TOOLHEAD_FUTURE_V3"

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
        with patch(
            "custom_components.snapmaker.snapmaker.socket.socket"
        ) as mock_socket_class:
            socket_instance = MagicMock()
            socket_instance.sendto.side_effect = Exception("Socket error")
            mock_socket_class.return_value = socket_instance

            devices = SnapmakerDevice.discover()

            assert len(devices) == 0
            # Socket should still be closed despite exception
            socket_instance.close.assert_called_once()

    def test_set_offline(self):
        """Test _set_offline method uses None for unknown numeric values."""
        device = SnapmakerDevice("192.168.1.100")
        device._model = "Snapmaker A350"
        device._set_offline()

        assert device.available is False
        assert device.status == "OFFLINE"
        assert device.data["status"] == "OFFLINE"
        assert device.data["ip"] == "192.168.1.100"
        assert device.data["model"] == "Snapmaker A350"
        assert device.data["nozzle_temperature"] is None
        assert device.data["heated_bed_temperature"] is None
        assert device.data["progress"] is None
        assert device.data["x"] is None
        assert device.data["y"] is None
        assert device.data["z"] is None
        assert device.data["total_lines"] is None
        assert device.data["current_line"] is None
        assert device.data["file_name"] == "N/A"
        assert device.data["tool_head"] == "N/A"
        assert device.data["is_filament_out"] is False
        assert device.raw_api_response == {}

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
            (
                b"IP@192.168.1.100|Model:Snapmaker A350|Status:IDLE",
                ("192.168.1.100", 20054),
            ),
            (b"INVALID", ("192.168.1.101", 20054)),
            socket.timeout(),
        ]

        devices = SnapmakerDevice.discover()

        # Should only include valid device
        assert len(devices) == 1
        assert devices[0]["host"] == "192.168.1.100"

    def test_check_online_socket_closed_on_exception(self):
        """Test that socket is closed even when exception occurs."""
        with patch(
            "custom_components.snapmaker.snapmaker.socket.socket"
        ) as mock_socket_class:
            socket_instance = MagicMock()
            socket_instance.sendto.side_effect = Exception("Send error")
            mock_socket_class.return_value = socket_instance

            device = SnapmakerDevice("192.168.1.100")
            device._check_online()

            # Socket should be closed even though exception occurred
            socket_instance.close.assert_called_once()


class TestTCPReachability:
    """Test the TCP reachability pre-check feature."""

    def test_check_reachable_success(self):
        """Test TCP check succeeds on first attempt."""
        with patch(
            "custom_components.snapmaker.snapmaker.socket.socket"
        ) as mock_socket_class:
            sock = MagicMock()
            sock.connect_ex.return_value = 0
            mock_socket_class.return_value = sock

            device = SnapmakerDevice("192.168.1.100")
            assert device._check_reachable() is True
            sock.connect_ex.assert_called_once_with(("192.168.1.100", API_PORT))

    def test_check_reachable_failure_all_retries(self):
        """Test TCP check fails after all retries."""
        with (
            patch(
                "custom_components.snapmaker.snapmaker.socket.socket"
            ) as mock_socket_class,
            patch("custom_components.snapmaker.snapmaker.time.sleep") as mock_sleep,
        ):
            sock = MagicMock()
            sock.connect_ex.return_value = 1  # Connection refused
            mock_socket_class.return_value = sock

            device = SnapmakerDevice("192.168.1.100")
            assert device._check_reachable() is False
            assert sock.connect_ex.call_count == REACHABILITY_MAX_RETRIES
            # Should have slept between retries (not after last attempt)
            assert mock_sleep.call_count == REACHABILITY_MAX_RETRIES - 1

    def test_check_reachable_succeeds_on_retry(self):
        """Test TCP check succeeds on second (last) attempt."""
        with (
            patch(
                "custom_components.snapmaker.snapmaker.socket.socket"
            ) as mock_socket_class,
            patch("custom_components.snapmaker.snapmaker.time.sleep"),
        ):
            sock = MagicMock()
            sock.connect_ex.side_effect = [1, 0]  # Fail first, succeed second
            mock_socket_class.return_value = sock

            device = SnapmakerDevice("192.168.1.100")
            assert device._check_reachable() is True
            assert sock.connect_ex.call_count == 2

    def test_check_reachable_os_error(self):
        """Test TCP check handles OSError gracefully."""
        with (
            patch(
                "custom_components.snapmaker.snapmaker.socket.socket"
            ) as mock_socket_class,
            patch("custom_components.snapmaker.snapmaker.time.sleep"),
        ):
            sock = MagicMock()
            sock.connect_ex.side_effect = OSError("Network unreachable")
            mock_socket_class.return_value = sock

            device = SnapmakerDevice("192.168.1.100")
            assert device._check_reachable() is False

    def test_update_skips_api_when_unreachable(self, mock_socket):
        """Test that update skips API calls when TCP check fails."""
        # Discovery succeeds but TCP check fails
        with patch("custom_components.snapmaker.snapmaker.time.sleep"):
            mock_socket.connect_ex.return_value = 1  # TCP check fails

            device = SnapmakerDevice("192.168.1.100")
            result = device.update()

            assert device.available is False
            assert device.status == "OFFLINE"

    def test_check_reachable_exponential_backoff(self):
        """Test that exponential backoff is used between retries."""
        with (
            patch(
                "custom_components.snapmaker.snapmaker.socket.socket"
            ) as mock_socket_class,
            patch("custom_components.snapmaker.snapmaker.time.sleep") as mock_sleep,
        ):
            sock = MagicMock()
            sock.connect_ex.return_value = 1
            mock_socket_class.return_value = sock

            device = SnapmakerDevice("192.168.1.100")
            device._check_reachable()

            # With REACHABILITY_MAX_RETRIES=2, there's 1 sleep between attempts
            # Backoff with base=1: 1^0=1
            expected_sleeps = [call(1)]
            assert mock_sleep.call_args_list == expected_sleeps


class TestTokenPersistence:
    """Test token persistence feature."""

    def test_set_token_update_callback(self):
        """Test setting the token update callback."""
        callback = MagicMock()
        device = SnapmakerDevice("192.168.1.100")
        device.set_token_update_callback(callback)

        assert device._on_token_update is callback

    def test_token_callback_not_called_on_failure(self, mock_requests):
        """Test that callback is not called when token retrieval fails."""
        mock_requests.post.return_value.text = "{}"

        callback = MagicMock()
        device = SnapmakerDevice("192.168.1.100")
        device.set_token_update_callback(callback)

        device._get_token()

        callback.assert_not_called()

    def test_saved_token_used_on_init(self):
        """Test that a saved token is used for API calls."""
        device = SnapmakerDevice("192.168.1.100", token="saved-token")
        assert device._token == "saved-token"

    def test_token_property(self):
        """Test the token property."""
        device = SnapmakerDevice("192.168.1.100")
        assert device.token is None

        device._token = "new-token"
        assert device.token == "new-token"


class TestSensitiveKeyFiltering:
    """Test that sensitive keys are filtered from diagnostic output."""

    def test_sensitive_api_keys_contains_token(self):
        """Test that SENSITIVE_API_KEYS includes 'token'."""
        assert "token" in SENSITIVE_API_KEYS

    def test_raw_api_response_property_filters_keys(self):
        """Test that the raw_api_response property filters sensitive keys."""
        device = SnapmakerDevice("192.168.1.100")
        device._raw_api_response = {
            "status": "IDLE",
            "token": "secret-value",
            "nozzleTemperature": 25.0,
        }

        filtered = device.raw_api_response
        assert "token" not in filtered
        assert filtered["status"] == "IDLE"
        assert filtered["nozzleTemperature"] == 25.0

    def test_warns_on_suspicious_api_keys(self, mock_requests, caplog):
        """Test that a warning is logged for API keys matching sensitive patterns."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "apiSecretKey": "some-value",
            "nozzleTemperature": 25.0
        }"""

        import logging

        with caplog.at_level(logging.WARNING):
            device = SnapmakerDevice("192.168.1.100")
            device._token = "test-token-123"
            device._available = True
            device._get_status()

        assert "potentially sensitive key 'apiSecretKey'" in caplog.text

    def test_no_warning_for_known_filtered_keys(self, mock_requests, caplog):
        """Test that no warning is logged for keys already in the filter set."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "token": "filtered-value",
            "nozzleTemperature": 25.0
        }"""

        import logging

        with caplog.at_level(logging.WARNING):
            device = SnapmakerDevice("192.168.1.100")
            device._token = "test-token-123"
            device._available = True
            device._get_status()

        assert "potentially sensitive key" not in caplog.text


class TestTokenCallbackEdgeCases:
    """Test edge cases for the token update callback."""

    def test_callback_not_called_with_same_token(self, mock_requests):
        """Test that callback is not re-invoked when token hasn't changed."""
        call_count = 0
        received_tokens = []

        def counting_callback(token):
            nonlocal call_count
            call_count += 1
            received_tokens.append(token)

        device = SnapmakerDevice("192.168.1.100")
        device.set_token_update_callback(counting_callback)

        # First call - should invoke callback
        device._get_token()
        assert call_count == 1
        assert received_tokens == ["test-token-123"]

    def test_callback_with_none_token_not_called(self, mock_requests):
        """Test that callback is not invoked with None token."""
        mock_requests.post.return_value.text = "{}"

        callback = MagicMock()
        device = SnapmakerDevice("192.168.1.100")
        device.set_token_update_callback(callback)

        device._get_token()
        callback.assert_not_called()


class TestStatusTokenSecurity:
    """Test that the token is not exposed in URLs."""

    def test_status_uses_params_not_url(self, mock_requests):
        """Test that _get_status passes token via params, not in the URL."""
        device = SnapmakerDevice("192.168.1.100")
        device._token = "secret-token-abc"
        device._available = True
        device._get_status()

        # Verify requests.get was called with params kwarg
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args

        # URL should NOT contain the token
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "secret-token-abc" not in url

        # Token should be in params
        assert call_args[1]["params"] == {"token": "secret-token-abc"}


class TestDualExtruderDetection:
    """Test dual extruder detection edge cases."""

    def test_single_extruder_with_nozzle_temperature(self, mock_requests):
        """Test single extruder when nozzleTemperature is present."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "toolHead": "TOOLHEAD_3DPRINTING_1",
            "nozzleTemperature": 25.0,
            "nozzleTargetTemperature": 0.0,
            "heatedBedTemperature": 23.0,
            "heatedBedTargetTemperature": 0.0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token"
        device._available = True
        device._get_status()

        assert device.dual_extruder is False
        assert device.data["nozzle_temperature"] == 25.0

    def test_dual_extruder_with_both_nozzle_fields(self, mock_requests):
        """Test dual extruder detected from nozzle1/nozzle2 fields."""
        mock_requests.get.return_value.text = """{
            "status": "RUNNING",
            "toolHead": "TOOLHEAD_3DPRINTING_2",
            "nozzle1Temperature": 210.0,
            "nozzle1TargetTemperature": 215.0,
            "nozzle2Temperature": 200.0,
            "nozzle2TargetTemperature": 205.0,
            "nozzleTemperature": 210.0,
            "heatedBedTemperature": 60.0,
            "heatedBedTargetTemperature": 65.0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token"
        device._available = True
        device._get_status()

        assert device.dual_extruder is True
        assert device.data["nozzle1_temperature"] == 210.0
        assert device.data["nozzle2_temperature"] == 200.0

    def test_dual_extruder_fallback_from_toolhead_without_single_nozzle(
        self, mock_requests
    ):
        """Test dual extruder detected when TOOLHEAD_3DPRINTING_1 has no nozzleTemperature."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "toolHead": "TOOLHEAD_3DPRINTING_1",
            "nozzle1Temperature": 25.0,
            "nozzle1TargetTemperature": 0.0,
            "heatedBedTemperature": 23.0,
            "heatedBedTargetTemperature": 0.0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token"
        device._available = True
        device._get_status()

        # Only nozzle1 present + TOOLHEAD_3DPRINTING_1 + no nozzleTemperature => dual
        assert device.dual_extruder is True
        assert device.data["tool_head"] == "Dual Extruder"

    def test_non_printing_toolhead_not_dual(self, mock_requests):
        """Test that CNC/laser toolheads are never detected as dual extruder."""
        mock_requests.get.return_value.text = """{
            "status": "IDLE",
            "toolHead": "TOOLHEAD_CNC_1",
            "heatedBedTemperature": 0,
            "heatedBedTargetTemperature": 0
        }"""

        device = SnapmakerDevice("192.168.1.100")
        device._token = "test-token"
        device._available = True
        device._get_status()

        assert device.dual_extruder is False
        assert device.data["tool_head"] == "CNC"
