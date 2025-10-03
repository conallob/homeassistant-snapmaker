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

    def _check_online(self) -> None:
        """Check if device is online via discovery."""
        udp_socket = socket.socket(family=socket.AF_INET,
                                   type=socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.settimeout(SOCKET_TIMEOUT)

        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                # Send discovery message
                udp_socket.sendto(DISCOVER_MESSAGE, (self._host, DISCOVER_PORT))

                # Wait for response
                reply, _ = udp_socket.recvfrom(BUFFER_SIZE)

                # Parse response
                elements = str(reply).split('|')
                sn_ip = (elements[0]).replace("'", "")
                sn_model = (elements[1]).replace("'", "")
                sn_status = (elements[2]).replace("'", "")

                _, sn_ip_val = sn_ip.split('@')
                _, sn_model_val = sn_model.split(':')
                _, sn_status_val = sn_status.split(':')

                # Update device info
                self._available = True
                self._model = sn_model_val
                self._status = sn_status_val
                self._data = {
                    "ip": sn_ip_val,
                    "model": sn_model_val,
                    "status": sn_status_val
                }

                break
            except socket.timeout:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
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
            except Exception as err:
                _LOGGER.error("Error checking Snapmaker status: %s", err)
                self._available = False
                self._status = "OFFLINE"
                break

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
            nozzle_temp = data.get("nozzleTemperature", 0)
            nozzle_target_temp = data.get("nozzleTargetTemperature", 0)
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
            self._data.update({
                "status": status,
                "nozzle_temperature": nozzle_temp,
                "nozzle_target_temperature": nozzle_target_temp,
                "heated_bed_temperature": bed_temp,
                "heated_bed_target_temperature": bed_target_temp,
                "file_name": file_name,
                "progress": progress,
                "elapsed_time": elapsed_time,
                "remaining_time": remaining_time
            })
        except Exception as err:
            _LOGGER.error("Error getting status from Snapmaker: %s", err)
            self._available = False
            self._status = "OFFLINE"

    @staticmethod
    def discover() -> list:
        """Discover Snapmaker devices on the network."""
        devices = []

        try:
            udp_socket = socket.socket(family=socket.AF_INET,
                                       type=socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(SOCKET_TIMEOUT)

            # Send discovery message to broadcast address
            udp_socket.sendto(DISCOVER_MESSAGE,
                              ("255.255.255.255", DISCOVER_PORT))

            # Try to receive responses
            try:
                while True:
                    reply, addr = udp_socket.recvfrom(BUFFER_SIZE)

                    # Parse response
                    elements = str(reply).split('|')
                    sn_ip = (elements[0]).replace("'", "")
                    sn_model = (elements[1]).replace("'", "")
                    sn_status = (elements[2]).replace("'", "")

                    _, sn_ip_val = sn_ip.split('@')
                    _, sn_model_val = sn_model.split(':')
                    _, sn_status_val = sn_status.split(':')

                    devices.append({
                        "host": sn_ip_val,
                        "model": sn_model_val,
                        "status": sn_status_val
                    })
            except socket.timeout:
                # No more responses
                pass
        except Exception as err:
            _LOGGER.error("Error discovering Snapmaker devices: %s", err)

        return devices
