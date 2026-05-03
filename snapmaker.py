"""Snapmaker device communication module."""

from datetime import timedelta
import json
import logging
import socket
import time
from typing import Any, Callable, Dict, Optional

import requests

from .const import TOOLHEAD_MAP, TOOLHEAD_TYPE_DUAL_EXTRUDER

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

# How many times to retry status after token approval before giving up
STATUS_WARMUP_RETRIES = 6
STATUS_WARMUP_DELAY = 3  # seconds between retries


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
        self._toolhead_type: Optional[str] = None
        self._on_token_update: Optional[Callable[[str], None]] = None
        self._token_invalid = False

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
    def toolhead_type(self) -> Optional[str]:
        """Return the toolhead type (persists across offline states)."""
        return self._toolhead_type

    @property
    def token(self) -> Optional[str]:
        """Return the current authentication token."""
        return self._token

    @property
    def token_invalid(self) -> bool:
        """Return True if token is invalid and needs reauth."""
        return self._token_invalid

    def set_token_update_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback to be called when token is updated."""
        self._on_token_update = callback

    def _check_reachable(self) -> bool:
        """Check if the device API port is reachable via TCP."""
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
        """Set device to offline state with default values."""
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
            "homed": False,
            "offset_x": None,
            "offset_y": None,
            "offset_z": None,
            "is_filament_out": False,
            "is_door_open": False,
            "has_enclosure": False,
            "has_rotary_module": False,
            "has_emergency_stop": False,
            "has_air_purifier": False,
            "total_lines": None,
            "current_line": None,
            "work_speed": None,
            "print_status": None,
        }

    def _check_online(self) -> None:
        """Check if device is online via UDP discovery."""
        udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(SOCKET_TIMEOUT)

        try:
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    udp_socket.sendto(
                        DISCOVER_MESSAGE, ("255.255.255.255", DISCOVER_PORT)
                    )

                    found = False

                    while True:
                        try:
                            reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

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

                                if (
                                    "@" not in sn_ip
                                    or ":" not in sn_model
                                    or ":" not in sn_status
                                ):
                                    _LOGGER.warning(
                                        "Malformed discovery response: %s", response_str
                                    )
                                    continue

                                _, sn_ip_val = sn_ip.split("@", 1)
                                _, sn_model_val = sn_model.split(":", 1)
                                _, sn_status_val = sn_status.split(":", 1)

                                if sn_ip_val == self._host or addr[0] == self._host:
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
                            break

                    if found:
                        break

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

            if retry_count >= MAX_RETRIES:
                _LOGGER.warning(
                    "Failed to discover device %s after %d attempts, marking offline",
                    self._host,
                    MAX_RETRIES,
                )
                self._set_offline()

        finally:
            udp_socket.close()

    def _connect_with_token(self, token: str) -> bool:
        """Reconnect to the device using an existing known token.

        Uses form-encoded POST (same as Luban) rather than JSON.
        Returns True if the token was accepted.
        """
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/connect"
            response = requests.post(
                url,
                data=f"token={token}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=API_TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("token") == token:
                    _LOGGER.debug("Reconnected to Snapmaker using existing token")
                    return True
            _LOGGER.warning(
                "Token reconnect failed: HTTP %d", response.status_code
            )
            return False
        except Exception as err:
            _LOGGER.error("Error reconnecting with token: %s", err)
            return False

    def _get_status_with_retry(self, retries: int = STATUS_WARMUP_RETRIES, delay: int = STATUS_WARMUP_DELAY) -> bool:
        """Attempt to get status, retrying if the response is empty.

        The Snapmaker API returns an empty body for a short period after
        a new token is approved. This method retries to handle that window.

        Returns True if status was successfully retrieved.
        """
        for attempt in range(retries):
            if attempt > 0:
                _LOGGER.debug(
                    "Status warmup retry %d/%d for %s", attempt + 1, retries, self._host
                )
                time.sleep(delay)

            url = f"http://{self._host}:{API_PORT}/api/v1/status"
            try:
                response = requests.get(
                    url, params={"token": self._token}, timeout=API_TIMEOUT
                )

                if response.status_code == 401:
                    _LOGGER.error("Token authentication failed (401 Unauthorized)")
                    self._token_invalid = True
                    self._available = False
                    self._status = "OFFLINE"
                    return False

                # Empty body = session not yet ready, retry
                if not response.text or response.text.strip() == "":
                    _LOGGER.debug(
                        "Empty status response from %s (attempt %d/%d), retrying...",
                        self._host,
                        attempt + 1,
                        retries,
                    )
                    continue

                response.raise_for_status()
                self._parse_status(response.json())
                return True

            except requests.exceptions.HTTPError as http_err:
                _LOGGER.error("HTTP error getting status: %s", http_err)
                return False
            except (json.JSONDecodeError, ValueError) as json_err:
                _LOGGER.error("Invalid JSON in status response: %s", json_err)
                return False
            except Exception as err:
                _LOGGER.error("Error getting status: %s", err)
                return False

        _LOGGER.warning(
            "Status still empty after %d retries for %s", retries, self._host
        )
        return False

    def generate_token(
        self, max_attempts: int = 18, poll_interval: int = 10
    ) -> Optional[str]:
        """Generate a new authentication token from Snapmaker device.

        Polls until the user approves the connection on the touchscreen.
        After approval, reconnects using form-encoded POST (same as Luban).
        """
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/connect"

            # Step 1: Request a new token (no token in body = triggers touchscreen prompt)
            _LOGGER.info("Requesting new token from Snapmaker at %s", self._host)
            response = requests.post(url, timeout=API_TIMEOUT)

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                _LOGGER.error(
                    "HTTP error requesting token: %s. Response: %s",
                    http_err,
                    response.text[:200],
                )
                return None

            try:
                token = json.loads(response.text).get("token")
            except (json.JSONDecodeError, ValueError) as json_err:
                _LOGGER.error(
                    "Failed to parse token response: %s. Response: %s",
                    json_err,
                    response.text[:200],
                )
                return None

            if not token:
                _LOGGER.error("No token received from Snapmaker")
                return None

            _LOGGER.info(
                "Token received (%s...), waiting for touchscreen approval...", token[:8]
            )

            # Step 2: Poll with form-encoded POST until the touchscreen is approved
            # The printer returns the same token back once approved
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        time.sleep(poll_interval)

                    response = requests.post(
                        url,
                        data=f"token={token}",
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=API_TIMEOUT,
                    )

                    response.raise_for_status()

                    try:
                        response_data = json.loads(response.text)
                        if response_data.get("token") == token:
                            _LOGGER.info("Token approved on touchscreen")
                            self._token = token
                            self._token_invalid = False
                            if self._on_token_update:
                                self._on_token_update(token)
                            return token
                    except (json.JSONDecodeError, ValueError):
                        continue

                except requests.exceptions.HTTPError as http_err:
                    # 403 means another connection attempt is in progress - keep waiting
                    if response.status_code == 403:
                        _LOGGER.debug(
                            "403 on token poll attempt %d/%d - another connection in progress, waiting",
                            attempt + 1,
                            max_attempts,
                        )
                        continue
                    _LOGGER.debug(
                        "HTTP error on token poll attempt %d/%d: %s",
                        attempt + 1,
                        max_attempts,
                        http_err,
                    )
                    continue
                except requests.exceptions.RequestException as req_err:
                    _LOGGER.debug(
                        "Network error on attempt %d/%d: %s",
                        attempt + 1,
                        max_attempts,
                        req_err,
                    )
                    continue

            _LOGGER.warning(
                "Token validation failed after %d attempts. "
                "User may not have authorized on touchscreen.",
                max_attempts,
            )
            return None

        except requests.exceptions.RequestException as req_err:
            _LOGGER.error("Network error requesting token from Snapmaker: %s", req_err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error generating token: %s", err)
            return None

    def _get_token(self) -> Optional[str]:
        """Get authentication token using an existing known token (no touchscreen needed).

        Uses form-encoded POST like Luban. Falls back to generate_token() if
        no token is known.
        """
        self._token_invalid = False

        if self._token:
            # Try reconnecting with the existing token first
            if self._connect_with_token(self._token):
                return self._token
            _LOGGER.warning(
                "Existing token rejected by %s, will need to generate new token",
                self._host,
            )
            self._token = None

        # No valid token - initiate new token flow (requires touchscreen approval)
        return self.generate_token()

    def _get_status(self) -> None:
        """Get status from Snapmaker device."""
        self._get_status_with_retry(retries=1, delay=0)

    def _parse_status(self, data: dict) -> None:
        """Parse the status API response and update device state."""
        # Store the raw API response for diagnostic purposes
        self._raw_api_response = data

        # Warn about any new keys that look sensitive
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

        status = data.get("status")

        raw_toolhead = data.get("toolHead", "")
        tool_head = TOOLHEAD_MAP.get(raw_toolhead, raw_toolhead or "N/A")

        if raw_toolhead and raw_toolhead not in TOOLHEAD_MAP:
            _LOGGER.warning(
                "Unknown toolhead type '%s' from device %s",
                raw_toolhead,
                self._host,
            )

        has_nozzle1 = "nozzle1Temperature" in data
        has_nozzle2 = "nozzle2Temperature" in data
        self._dual_extruder = has_nozzle1 and has_nozzle2

        if (
            raw_toolhead == "TOOLHEAD_3DPRINTING_1"
            and "nozzleTemperature" not in data
            and has_nozzle1
        ):
            self._dual_extruder = True
            tool_head = TOOLHEAD_TYPE_DUAL_EXTRUDER

        if tool_head and tool_head != "N/A":
            self._toolhead_type = tool_head

        if self._dual_extruder:
            nozzle1_temp = data.get("nozzle1Temperature", 0)
            nozzle1_target_temp = data.get("nozzle1TargetTemperature", 0)
            nozzle2_temp = data.get("nozzle2Temperature", 0)
            nozzle2_target_temp = data.get("nozzle2TargetTemperature", 0)
        else:
            nozzle1_temp = data.get("nozzleTemperature", 0)
            nozzle1_target_temp = data.get("nozzleTargetTemperature", 0)
            nozzle2_temp = None
            nozzle2_target_temp = None

        bed_temp = data.get("heatedBedTemperature", 0)
        bed_target_temp = data.get("heatedBedTargetTemperature", 0)

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

        x = data.get("x", 0)
        y = data.get("y", 0)
        z = data.get("z", 0)
        offset_x = data.get("offsetX", 0)
        offset_y = data.get("offsetY", 0)
        offset_z = data.get("offsetZ", 0)

        # homed is a boolean in the API
        homed = data.get("homed", False)

        is_filament_out = data.get("isFilamentOut", False)

        # Door state field is isEnclosureDoorOpen, not isDoorOpen
        is_door_open = data.get("isEnclosureDoorOpen", False)

        # Module presence flags are nested inside moduleList
        module_list = data.get("moduleList", {})
        has_enclosure = module_list.get("enclosure", False)
        has_rotary_module = module_list.get("rotaryModule", False)
        has_emergency_stop = module_list.get("emergencyStopButton", False)
        has_air_purifier = module_list.get("airPurifier", False)

        total_lines = data.get("totalLines", 0)
        current_line = data.get("currentLine", 0)

        work_speed = data.get("workSpeed")
        print_status = data.get("printStatus")

        spindle_speed = data.get("spindleSpeed")
        laser_power = data.get("laserPower")
        laser_focal_length = data.get("laserFocalLength")

        self._status = status
        self._available = True

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
            "offset_x": offset_x,
            "offset_y": offset_y,
            "offset_z": offset_z,
            "homed": homed,
            "is_filament_out": is_filament_out,
            "is_door_open": is_door_open,
            "has_enclosure": has_enclosure,
            "has_rotary_module": has_rotary_module,
            "has_emergency_stop": has_emergency_stop,
            "has_air_purifier": has_air_purifier,
            "total_lines": total_lines,
            "current_line": current_line,
            "work_speed": work_speed,
            "print_status": print_status,
        }

        if spindle_speed is not None:
            update_dict["spindle_speed"] = spindle_speed
        if laser_power is not None:
            update_dict["laser_power"] = laser_power
        if laser_focal_length is not None:
            update_dict["laser_focal_length"] = laser_focal_length

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

    @staticmethod
    def discover() -> list:
        """Discover Snapmaker devices on the network."""
        devices = []
        udp_socket = None

        try:
            udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(SOCKET_TIMEOUT)
            udp_socket.sendto(DISCOVER_MESSAGE, ("255.255.255.255", DISCOVER_PORT))

            try:
                while True:
                    reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

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

                        if (
                            "@" not in sn_ip
                            or ":" not in sn_model
                            or ":" not in sn_status
                        ):
                            _LOGGER.warning(
                                "Malformed discovery response: %s", response_str
                            )
                            continue

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
                pass
        except Exception as err:
            _LOGGER.error("Error discovering Snapmaker devices: %s", err)
        finally:
            if udp_socket is not None:
                udp_socket.close()

        return devices
