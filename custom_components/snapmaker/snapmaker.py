"""Snapmaker device communication module."""

from datetime import timedelta
import json
import logging
import socket
import time
from typing import Any, Callable, Dict, Optional

import requests

from .const import TOOLHEAD_MAP

_LOGGER = logging.getLogger(__name__)

# Network configuration constants
DISCOVER_PORT = 20054
DISCOVER_MESSAGE = b"discover"
SOCKET_TIMEOUT = 1.0  # Seconds to wait for UDP responses
MAX_RETRIES = 5  # Number of discovery attempts before marking device offline
RETRY_DELAY = 0.5  # Seconds to wait between discovery retry attempts
BUFFER_SIZE = 1024  # UDP receive buffer size in bytes
API_TIMEOUT = 5  # Seconds to wait for HTTP API responses
API_PORT = 8080  # Default HTTP API port
TCP_CHECK_TIMEOUT = 1.0  # Seconds to wait for TCP reachability check
REACHABILITY_MAX_RETRIES = 2  # Max retries for reachability check
# Base for exponential backoff (seconds). Kept low because time.sleep()
# blocks the executor thread during the coordinator update cycle.
REACHABILITY_BACKOFF_BASE = 1

# Keys to strip from the raw API response before exposing as diagnostic attributes
SENSITIVE_API_KEYS = {"token"}

# Patterns that indicate potentially sensitive API keys
_SENSITIVE_KEY_PATTERNS = ("token", "password", "secret", "key", "credential")


class SnapmakerDevice:
    """Class to communicate with a Snapmaker device."""

    def __init__(self, host: str, token: Optional[str] = None):
        """Initialize the Snapmaker device."""
        self._host = host
        self._token = token
        self._data: Dict[str, Any] = {}
        self._raw_api_response: Dict[str, Any] = {}
        self._available = False
        self._model = None
        self._status = "OFFLINE"
        self._dual_extruder = False
        self._on_token_update: Optional[Callable[[str], None]] = None

    @property
    def host(self) -> str:
        """Return the host of the device."""
        return self._host

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def model(self) -> Optional[str]:
        """Return the model of the device."""
        return self._model

    @property
    def status(self) -> str:
        """Return the status of the device."""
        return self._status

    @property
    def data(self) -> Dict[str, Any]:
        """Return the data of the device."""
        return self._data

    @property
    def raw_api_response(self) -> Dict[str, Any]:
        """Return the raw API response for diagnostic purposes.

        Sensitive keys (e.g. token) are stripped before returning.
        """
        return {
            k: v
            for k, v in self._raw_api_response.items()
            if k not in SENSITIVE_API_KEYS
        }

    @property
    def dual_extruder(self) -> bool:
        """Return True if device has dual extruder."""
        return self._dual_extruder

    @property
    def token(self) -> Optional[str]:
        """Return the current authentication token."""
        return self._token

    def set_token_update_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback to be called when token is updated."""
        self._on_token_update = callback

    def _check_reachable(self) -> bool:
        """Check if the device API port is reachable via TCP.

        Performs a lightweight TCP connection check before attempting
        full HTTP API calls. Uses exponential backoff on retries.
        Note: time.sleep() blocks the executor thread during retries.

        Returns:
            True if the device is reachable, False otherwise.
        """
        for attempt in range(REACHABILITY_MAX_RETRIES):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(TCP_CHECK_TIMEOUT)
                result = sock.connect_ex((self._host, API_PORT))
                sock.close()
                if result == 0:
                    return True
            except OSError:
                pass

            if attempt < REACHABILITY_MAX_RETRIES - 1:
                backoff = REACHABILITY_BACKOFF_BASE**attempt
                _LOGGER.debug(
                    "TCP check failed for %s:%d (attempt %d/%d), retrying in %ds",
                    self._host,
                    API_PORT,
                    attempt + 1,
                    REACHABILITY_MAX_RETRIES,
                    backoff,
                )
                # Blocking sleep - runs in executor thread, not the event loop
                time.sleep(backoff)

        _LOGGER.debug(
            "Device %s:%d not reachable after %d TCP checks",
            self._host,
            API_PORT,
            REACHABILITY_MAX_RETRIES,
        )
        return False

    def update(self) -> Dict[str, Any]:
        """Update device data."""
        # First check if device is online via discovery
        self._check_online()

        # If device is online and we have a token, get detailed status
        if self._available and self._status != "OFFLINE":
            # TCP reachability pre-check before making HTTP calls
            if not self._check_reachable():
                _LOGGER.warning(
                    "Device %s discovered but API port %d not reachable",
                    self._host,
                    API_PORT,
                )
                self._set_offline()
                return self._data

            if not self._token:
                self._token = self._get_token()

            if self._token:
                self._get_status()

        return self._data

    def _set_offline(self) -> None:
        """Set device to offline state with default values.

        Uses None for numeric values that are unknown when offline,
        allowing HA to display "unknown" rather than misleading zeros.
        """
        self._available = False
        self._status = "OFFLINE"
        self._raw_api_response = {}
        self._data = {
            "ip": self._host,
            "model": self._model or "N/A",
            "status": "OFFLINE",
            "nozzle_temperature": None,
            "nozzle_target_temperature": None,
            "heated_bed_temperature": None,
            "heated_bed_target_temperature": None,
            "file_name": "N/A",
            "progress": None,
            "elapsed_time": "N/A",
            "remaining_time": "N/A",
            "estimated_time": "N/A",
            "tool_head": "N/A",
            "x": None,
            "y": None,
            "z": None,
            "homing": "N/A",
            "is_filament_out": False,
            "is_door_open": False,
            "has_enclosure": False,
            "has_rotary_module": False,
            "has_emergency_stop": False,
            "has_air_purifier": False,
            "total_lines": None,
            "current_line": None,
        }

    def _check_online(self) -> None:
        """Check if device is online via discovery.

        Note: A new UDP socket is created for each discovery attempt.
        This is intentional for UDP broadcast discovery as it avoids stale
        state and the overhead is minimal. For persistent connections,
        use the HTTP API with token authentication.
        """
        udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(SOCKET_TIMEOUT)

        try:
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    # Send discovery message to broadcast address
                    udp_socket.sendto(
                        DISCOVER_MESSAGE, ("255.255.255.255", DISCOVER_PORT)
                    )

                    # Wait for responses and filter for our target host
                    found = False

                    while True:
                        try:
                            reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

                            # Parse response - decode bytes properly
                            try:
                                response_str = reply.decode("utf-8")
                                elements = response_str.split("|")

                                if len(elements) < 3:
                                    _LOGGER.warning(
                                        "Invalid discovery response format: %s",
                                        response_str,
                                    )
                                    continue

                                sn_ip = elements[0]
                                sn_model = elements[1]
                                sn_status = elements[2]

                                # Parse fields with validation
                                if (
                                    "@" not in sn_ip
                                    or ":" not in sn_model
                                    or ":" not in sn_status
                                ):
                                    _LOGGER.warning(
                                        "Malformed discovery response: %s", response_str
                                    )
                                    continue

                                # Split and discard prefix (e.g., "IP@" becomes "192.168.1.100")
                                _, sn_ip_val = sn_ip.split("@", 1)
                                _, sn_model_val = sn_model.split(":", 1)
                                _, sn_status_val = sn_status.split(":", 1)

                                # Check if this response is from our target host
                                if sn_ip_val == self._host or addr[0] == self._host:
                                    # Update device info
                                    self._available = True
                                    self._model = sn_model_val
                                    self._status = sn_status_val
                                    self._data = {
                                        "ip": sn_ip_val,
                                        "model": sn_model_val,
                                        "status": sn_status_val,
                                    }
                                    found = True
                                    break
                            except (UnicodeDecodeError, ValueError) as parse_err:
                                _LOGGER.warning(
                                    "Failed to parse discovery response: %s", parse_err
                                )
                                continue

                        except socket.timeout:
                            # No more responses in this iteration
                            break

                    # Exit retry loop immediately if device was found
                    if found:
                        break

                    # If we didn't find our device, retry after a brief delay
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)

                except Exception as err:
                    _LOGGER.error(
                        "Error checking Snapmaker status (attempt %d/%d): %s",
                        retry_count + 1,
                        MAX_RETRIES,
                        err,
                    )
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)

            # If we exhausted all retries without finding the device, mark as offline
            if retry_count >= MAX_RETRIES:
                _LOGGER.warning(
                    "Failed to discover device %s after %d attempts, marking offline",
                    self._host,
                    MAX_RETRIES,
                )
                self._set_offline()

        finally:
            # Always close the socket, even if an exception occurred
            udp_socket.close()

    def _get_token(self) -> Optional[str]:
        """Get authentication token from Snapmaker device.

        Implements a two-step token acquisition process:
        1. POST to /api/v1/connect to request a token
        2. POST the received token back to validate it

        Returns:
            Optional[str]: Authentication token if successful, None otherwise
        """
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/connect"

            # First request to initiate connection
            response = requests.post(url, timeout=API_TIMEOUT)

            if "Failed" in response.text:
                _LOGGER.error("Failed to connect to Snapmaker: %s", response.text)
                return None

            # Extract token from response
            try:
                token = json.loads(response.text).get("token")
            except (json.JSONDecodeError, ValueError) as json_err:
                _LOGGER.error("Failed to parse token response: %s", json_err)
                return None

            if not token:
                _LOGGER.error("No token received from Snapmaker")
                return None

            # Second request to validate token
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            form_data = {"token": token}
            response = requests.post(
                url, data=form_data, headers=headers, timeout=API_TIMEOUT
            )

            # Validate token response with JSON error handling
            try:
                response_data = json.loads(response.text)
                if response_data.get("token") == token:
                    _LOGGER.info("Successfully connected to Snapmaker")
                    # Notify callback about new token for persistence
                    if self._on_token_update:
                        self._on_token_update(token)
                    return token
            except (json.JSONDecodeError, ValueError) as json_err:
                _LOGGER.error("Failed to parse token validation response: %s", json_err)
                return None

            _LOGGER.error("Token validation failed")
            return None
        except requests.exceptions.RequestException as req_err:
            _LOGGER.error("Network error getting token from Snapmaker: %s", req_err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error getting token from Snapmaker: %s", err)
            return None

    def _get_status(self) -> None:
        """Get status from Snapmaker device."""
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/status"
            response = requests.get(
                url, params={"token": self._token}, timeout=API_TIMEOUT
            )

            # Check if response is valid
            if not response.text or response.text.strip() == "":
                _LOGGER.error("Empty response from Snapmaker status API")
                self._available = False
                self._status = "OFFLINE"
                return

            # Check for HTTP errors
            response.raise_for_status()

            # Try to parse JSON
            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as json_err:
                _LOGGER.error(
                    "Invalid JSON response from Snapmaker: %s. Response text: %s",
                    json_err,
                    response.text[:200],
                )
                self._available = False
                self._status = "OFFLINE"
                return

            # Store the raw API response for diagnostic purposes
            self._raw_api_response = data

            # Warn about any new keys that look sensitive but aren't in our filter set
            for api_key in data:
                if api_key not in SENSITIVE_API_KEYS and any(
                    pattern in api_key.lower() for pattern in _SENSITIVE_KEY_PATTERNS
                ):
                    _LOGGER.warning(
                        "API response from %s contains potentially sensitive key '%s' "
                        "that is not in the filter set",
                        self._host,
                        api_key,
                    )

            # Extract status data
            status = data.get("status")

            # Determine toolhead type
            raw_toolhead = data.get("toolHead", "")
            tool_head = TOOLHEAD_MAP.get(raw_toolhead, raw_toolhead or "N/A")

            # Log unknown toolhead types for debugging
            if raw_toolhead and raw_toolhead not in TOOLHEAD_MAP:
                _LOGGER.warning(
                    "Unknown toolhead type '%s' from device %s, "
                    "using raw value as display name",
                    raw_toolhead,
                    self._host,
                )

            # Check for dual extruder configuration
            # Dual extruders have nozzle1Temperature and nozzle2Temperature fields
            has_nozzle1 = "nozzle1Temperature" in data
            has_nozzle2 = "nozzle2Temperature" in data
            self._dual_extruder = has_nozzle1 and has_nozzle2

            # If toolhead is 3D printing v1 but no single nozzleTemperature,
            # it's a dual extruder
            if (
                raw_toolhead == "TOOLHEAD_3DPRINTING_1"
                and "nozzleTemperature" not in data
                and has_nozzle1
            ):
                self._dual_extruder = True
                tool_head = "Dual Extruder"
                _LOGGER.debug(
                    "Dual extruder fallback triggered for %s: "
                    "toolHead=%s, nozzleTemperature absent, "
                    "nozzle1Temperature present=%s, nozzle2Temperature present=%s",
                    self._host,
                    raw_toolhead,
                    has_nozzle1,
                    has_nozzle2,
                )

            if self._dual_extruder:
                _LOGGER.debug("Detected dual extruder configuration for %s", self._host)

            # Extract temperature data based on configuration
            if self._dual_extruder:
                nozzle1_temp = data.get("nozzle1Temperature", 0)
                nozzle1_target_temp = data.get("nozzle1TargetTemperature", 0)
                nozzle2_temp = data.get("nozzle2Temperature", 0)
                nozzle2_target_temp = data.get("nozzle2TargetTemperature", 0)
            else:
                # Single nozzle configuration
                nozzle1_temp = data.get("nozzleTemperature", 0)
                nozzle1_target_temp = data.get("nozzleTargetTemperature", 0)
                nozzle2_temp = None
                nozzle2_target_temp = None

            bed_temp = data.get("heatedBedTemperature", 0)
            bed_target_temp = data.get("heatedBedTargetTemperature", 0)

            # Extract print job data
            file_name = data.get("fileName", "N/A")
            progress = 0
            if data.get("progress") is not None:
                progress = round(data.get("progress") * 100, 1)

            elapsed_time = "00:00:00"
            if data.get("elapsedTime") is not None:
                elapsed_time = str(timedelta(seconds=data.get("elapsedTime")))

            remaining_time = "00:00:00"
            if data.get("remainingTime") is not None:
                remaining_time = str(timedelta(seconds=data.get("remainingTime")))

            estimated_time = "00:00:00"
            if data.get("estimatedTime") is not None:
                estimated_time = str(timedelta(seconds=data.get("estimatedTime")))

            # Extract position data
            x = data.get("x", 0)
            y = data.get("y", 0)
            z = data.get("z", 0)
            homing = data.get("homing", "N/A")

            # Extract module/safety data
            is_filament_out = data.get("isFilamentOut", False)
            is_door_open = data.get("isDoorOpen", False)
            has_enclosure = data.get("enclosure", False)
            has_rotary_module = data.get("rotaryModule", False)
            has_emergency_stop = data.get("emergencyStop", False)
            has_air_purifier = data.get("airPurifier", False)

            # Extract G-code line progress
            total_lines = data.get("totalLines", 0)
            current_line = data.get("currentLine", 0)

            # Extract CNC/Laser specific data
            spindle_speed = data.get("spindleSpeed")
            laser_power = data.get("laserPower")
            laser_focal_length = data.get("laserFocalLength")

            # Update device data
            self._status = status
            update_dict = {
                "status": status,
                "heated_bed_temperature": bed_temp,
                "heated_bed_target_temperature": bed_target_temp,
                "file_name": file_name,
                "progress": progress,
                "elapsed_time": elapsed_time,
                "remaining_time": remaining_time,
                "estimated_time": estimated_time,
                "tool_head": tool_head,
                "x": x,
                "y": y,
                "z": z,
                "homing": homing,
                "is_filament_out": is_filament_out,
                "is_door_open": is_door_open,
                "has_enclosure": has_enclosure,
                "has_rotary_module": has_rotary_module,
                "has_emergency_stop": has_emergency_stop,
                "has_air_purifier": has_air_purifier,
                "total_lines": total_lines,
                "current_line": current_line,
            }

            # Add CNC/Laser specific data only when relevant
            if spindle_speed is not None:
                update_dict["spindle_speed"] = spindle_speed
            if laser_power is not None:
                update_dict["laser_power"] = laser_power
            if laser_focal_length is not None:
                update_dict["laser_focal_length"] = laser_focal_length

            # Add nozzle data based on configuration
            if self._dual_extruder:
                update_dict.update(
                    {
                        "nozzle1_temperature": nozzle1_temp,
                        "nozzle1_target_temperature": nozzle1_target_temp,
                        "nozzle2_temperature": nozzle2_temp,
                        "nozzle2_target_temperature": nozzle2_target_temp,
                    }
                )
            else:
                update_dict.update(
                    {
                        "nozzle_temperature": nozzle1_temp,
                        "nozzle_target_temperature": nozzle1_target_temp,
                    }
                )

            self._data.update(update_dict)
        except requests.exceptions.HTTPError as http_err:
            if http_err.response is not None and http_err.response.status_code == 401:
                _LOGGER.warning(
                    "Token expired or invalid for %s, clearing token", self._host
                )
                self._token = None
                self._set_offline()
            else:
                _LOGGER.error("HTTP error getting status from Snapmaker: %s", http_err)
                self._set_offline()
        except Exception as err:
            _LOGGER.error("Error getting status from Snapmaker: %s", err)
            self._set_offline()

    @staticmethod
    def discover() -> list:
        """Discover Snapmaker devices on the network."""
        devices = []
        udp_socket = None

        try:
            # Create and configure socket inside try block to ensure cleanup
            udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(SOCKET_TIMEOUT)
            # Send discovery message to broadcast address
            udp_socket.sendto(DISCOVER_MESSAGE, ("255.255.255.255", DISCOVER_PORT))

            # Try to receive responses
            try:
                while True:
                    reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

                    # Parse response - decode bytes properly
                    try:
                        response_str = reply.decode("utf-8")
                        elements = response_str.split("|")

                        if len(elements) < 3:
                            _LOGGER.warning(
                                "Invalid discovery response format: %s", response_str
                            )
                            continue

                        sn_ip = elements[0]
                        sn_model = elements[1]
                        sn_status = elements[2]

                        # Parse fields with validation
                        if (
                            "@" not in sn_ip
                            or ":" not in sn_model
                            or ":" not in sn_status
                        ):
                            _LOGGER.warning(
                                "Malformed discovery response: %s", response_str
                            )
                            continue

                        # Split and discard prefix (e.g., "IP@" becomes "192.168.1.100")
                        _prefix, sn_ip_val = sn_ip.split("@", 1)
                        _prefix, sn_model_val = sn_model.split(":", 1)
                        _prefix, sn_status_val = sn_status.split(":", 1)

                        devices.append(
                            {
                                "host": sn_ip_val,
                                "model": sn_model_val,
                                "status": sn_status_val,
                            }
                        )
                    except (UnicodeDecodeError, ValueError) as parse_err:
                        _LOGGER.warning(
                            "Failed to parse discovery response: %s", parse_err
                        )
                        continue

            except socket.timeout:
                # No more responses
                pass
        except Exception as err:
            _LOGGER.error("Error discovering Snapmaker devices: %s", err)
        finally:
            # Always close the socket if it was created
            if udp_socket is not None:
                udp_socket.close()

        return devices
