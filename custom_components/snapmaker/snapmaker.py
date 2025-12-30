"""Snapmaker device communication module."""
import ipaddress
import json
import logging
import requests
import socket
from datetime import timedelta
from typing import Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)

DISCOVER_PORT = 20054
DISCOVER_MESSAGE = b'discover'
SOCKET_TIMEOUT = 1.0
MAX_RETRIES = 5
BUFFER_SIZE = 1024


class SnapmakerDevice:
    """Class to communicate with a Snapmaker device."""

    def __init__(self, host: str):
        """Initialize the Snapmaker device."""
        self._host = host
        self._token = None
        self._data = {}
        self._available = False
        self._model = None
        self._status = "OFFLINE"
        self._dual_extruder = False

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
    def dual_extruder(self) -> bool:
        """Return True if device has dual extruder."""
        return self._dual_extruder

    def update(self) -> Dict[str, Any]:
        """Update device data."""
        # First check if device is online via discovery
        self._check_online()

        # If device is online and we have a token, get detailed status
        if self._available and self._status != "OFFLINE":
            if not self._token:
                self._token = self._get_token()

            if self._token:
                self._get_status()

        return self._data

    def _set_offline(self) -> None:
        """Set device to offline state with default values."""
        self._available = False
        self._status = "OFFLINE"
        self._data = {
            "ip": self._host,
            "model": self._model or "N/A",
            "status": "OFFLINE",
            "nozzle_temperature": 0,
            "nozzle_target_temperature": 0,
            "heated_bed_temperature": 0,
            "heated_bed_target_temperature": 0,
            "file_name": "N/A",
            "progress": 0,
            "elapsed_time": "00:00:00",
            "remaining_time": "00:00:00"
        }

    def _check_online(self) -> None:
        """Check if device is online via discovery."""
        udp_socket = socket.socket(family=socket.AF_INET,
                                   type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(SOCKET_TIMEOUT)

        try:
            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    # Send discovery message to broadcast address
                    udp_socket.sendto(DISCOVER_MESSAGE, ("255.255.255.255", DISCOVER_PORT))

                    # Wait for responses and filter for our target host
                    found = False

                    while True:
                        try:
                            reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

                            # Parse response - decode bytes properly
                            try:
                                response_str = reply.decode('utf-8')
                                elements = response_str.split('|')

                                if len(elements) < 3:
                                    _LOGGER.warning("Invalid discovery response format: %s", response_str)
                                    continue

                                sn_ip = elements[0]
                                sn_model = elements[1]
                                sn_status = elements[2]

                                # Parse fields with validation
                                if '@' not in sn_ip or ':' not in sn_model or ':' not in sn_status:
                                    _LOGGER.warning("Malformed discovery response: %s", response_str)
                                    continue

                                _, sn_ip_val = sn_ip.split('@', 1)
                                _, sn_model_val = sn_model.split(':', 1)
                                _, sn_status_val = sn_status.split(':', 1)

                                # Check if this response is from our target host
                                if sn_ip_val == self._host or addr[0] == self._host:
                                    # Update device info
                                    self._available = True
                                    self._model = sn_model_val
                                    self._status = sn_status_val
                                    self._data = {
                                        "ip": sn_ip_val,
                                        "model": sn_model_val,
                                        "status": sn_status_val
                                    }
                                    found = True
                                    break
                            except (UnicodeDecodeError, ValueError) as parse_err:
                                _LOGGER.warning("Failed to parse discovery response: %s", parse_err)
                                continue

                        except socket.timeout:
                            # No more responses in this iteration
                            break

                    if found:
                        break

                    # If we didn't find our device, retry
                    retry_count += 1

                except Exception as err:
                    _LOGGER.error("Error checking Snapmaker status: %s", err)
                    retry_count += 1

            # If we exhausted all retries without finding the device, mark as offline
            if retry_count >= MAX_RETRIES:
                self._set_offline()

        finally:
            # Always close the socket, even if an exception occurred
            udp_socket.close()

    def _get_token(self) -> Optional[str]:
        """Get token from Snapmaker device."""
        try:
            url = f"http://{self._host}:8080/api/v1/connect"

            # First request to initiate connection
            response = requests.post(url, timeout=5)

            if "Failed" in response.text:
                _LOGGER.error("Failed to connect to Snapmaker: %s",
                              response.text)
                return None

            # Extract token from response
            token = json.loads(response.text).get("token")

            if not token:
                _LOGGER.error("No token received from Snapmaker")
                return None

            # Second request to validate token
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            form_data = {'token': token}
            response = requests.post(url, data=form_data, headers=headers,
                                     timeout=5)

            if json.loads(response.text).get("token") == token:
                _LOGGER.info("Successfully connected to Snapmaker")
                return token

            _LOGGER.error("Token validation failed")
            return None
        except Exception as err:
            _LOGGER.error("Error getting token from Snapmaker: %s", err)
            return None

    def _get_status(self) -> None:
        """Get status from Snapmaker device."""
        try:
            url = f"http://{self._host}:8080/api/v1/status?token={self._token}"
            response = requests.get(url, timeout=5)

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
                    json_err, response.text[:200])
                self._available = False
                self._status = "OFFLINE"
                return

            # Extract status data
            status = data.get("status")

            # Check for dual extruder configuration
            # Dual extruders have nozzle1Temperature and nozzle2Temperature fields
            has_nozzle1 = "nozzle1Temperature" in data
            has_nozzle2 = "nozzle2Temperature" in data
            self._dual_extruder = has_nozzle1 and has_nozzle2

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

            # Extract optional data
            file_name = data.get("fileName", "N/A")
            progress = 0
            if data.get("progress") is not None:
                progress = round(data.get("progress") * 100, 1)

            elapsed_time = "00:00:00"
            if data.get("elapsedTime") is not None:
                elapsed_time = str(timedelta(seconds=data.get("elapsedTime")))

            remaining_time = "00:00:00"
            if data.get("remainingTime") is not None:
                remaining_time = str(
                    timedelta(seconds=data.get("remainingTime")))

            # Update device data
            self._status = status
            update_dict = {
                "status": status,
                "heated_bed_temperature": bed_temp,
                "heated_bed_target_temperature": bed_target_temp,
                "file_name": file_name,
                "progress": progress,
                "elapsed_time": elapsed_time,
                "remaining_time": remaining_time
            }

            # Add nozzle data based on configuration
            if self._dual_extruder:
                update_dict.update({
                    "nozzle1_temperature": nozzle1_temp,
                    "nozzle1_target_temperature": nozzle1_target_temp,
                    "nozzle2_temperature": nozzle2_temp,
                    "nozzle2_target_temperature": nozzle2_target_temp,
                })
            else:
                update_dict.update({
                    "nozzle_temperature": nozzle1_temp,
                    "nozzle_target_temperature": nozzle1_target_temp,
                })

            self._data.update(update_dict)
        except Exception as err:
            _LOGGER.error("Error getting status from Snapmaker: %s", err)
            self._available = False
            self._status = "OFFLINE"

    @staticmethod
    def discover() -> list:
        """Discover Snapmaker devices on the network."""
        devices = []
        udp_socket = socket.socket(family=socket.AF_INET,
                                   type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(SOCKET_TIMEOUT)

        try:
            # Send discovery message to broadcast address
            udp_socket.sendto(DISCOVER_MESSAGE,
                              ("255.255.255.255", DISCOVER_PORT))

            # Try to receive responses
            try:
                while True:
                    reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

                    # Parse response - decode bytes properly
                    try:
                        response_str = reply.decode('utf-8')
                        elements = response_str.split('|')

                        if len(elements) < 3:
                            _LOGGER.warning("Invalid discovery response format: %s", response_str)
                            continue

                        sn_ip = elements[0]
                        sn_model = elements[1]
                        sn_status = elements[2]

                        # Parse fields with validation
                        if '@' not in sn_ip or ':' not in sn_model or ':' not in sn_status:
                            _LOGGER.warning("Malformed discovery response: %s", response_str)
                            continue

                        _, sn_ip_val = sn_ip.split('@', 1)
                        _, sn_model_val = sn_model.split(':', 1)
                        _, sn_status_val = sn_status.split(':', 1)

                        devices.append({
                            "host": sn_ip_val,
                            "model": sn_model_val,
                            "status": sn_status_val
                        })
                    except (UnicodeDecodeError, ValueError) as parse_err:
                        _LOGGER.warning("Failed to parse discovery response: %s", parse_err)
                        continue

            except socket.timeout:
                # No more responses
                pass
        except Exception as err:
            _LOGGER.error("Error discovering Snapmaker devices: %s", err)
        finally:
            # Always close the socket
            udp_socket.close()

        return devices
