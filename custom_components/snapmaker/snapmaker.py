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
# Some devices (e.g. Snapmaker 2.0 series) briefly return an empty status
# response while the touchscreen is dismissing the just-approved auth
# dialog. A couple of short retries avoids a spurious "cannot connect"
# right after token generation succeeds.
STATUS_EMPTY_RETRY_COUNT = 3
STATUS_EMPTY_RETRY_DELAY = 1.0  # Seconds between empty-response retries
# The device answers 403 to every connect while another client's connect or
# touchscreen approval is pending. A collision clears within a poll; a 403 that
# persists this many polls in a row (~5 min) means the device no longer accepts
# our token, so it is treated as rejected and reauth is requested.
BUSY_REAUTH_POLLS = 10

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
        self._toolhead_type: Optional[str] = None
        self._on_token_update: Optional[Callable[[str], None]] = None
        self._token_invalid = False
        self._unsupported_protocol_reason: Optional[str] = None
        # Set True right after a fresh token handshake succeeds, so the very
        # next _get_status() call retries on an empty body (the touchscreen
        # may still be dismissing the auth dialog). Consumed (cleared) by
        # that call so steady-state polling doesn't pay the retry cost.
        self._settle_retries_pending = False
        self._connected = (
            False  # True once _connect_with_token() succeeds; reset on offline/401
        )
        self._busy_polls = 0  # consecutive reconnects refused with 403

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
        """Return True if token is invalid and needs reauth.

        This flag is set to True when the device API returns a 401 Unauthorized
        response, indicating the current token has expired or been invalidated.
        When True, the integration's DataUpdateCoordinator will trigger a reauth
        flow, prompting the user to generate a new token via the touchscreen.

        The flag remains True until a new token is successfully generated and
        validated through the config flow's authorize step.

        Returns:
            bool: True if token needs reauthorization, False otherwise.
        """
        return self._token_invalid

    @property
    def unsupported_protocol_reason(self) -> Optional[str]:
        """Return why the device's firmware may not support the legacy HTTP API.

        Returns None if no such condition has been detected.

        Newer Snapmaker firmware (e.g. Artisan/J1 on recent firmware, and the
        Klipper-based U1) replaces or removes the legacy `/api/v1/connect` HTTP
        API in favor of a proprietary binary protocol (SACP) or a
        Moonraker/Klipper API, neither of which this integration implements yet.
        """
        return self._unsupported_protocol_reason

    def _classify_connect_failure(self, response: requests.Response) -> None:
        """Record a reason if a /api/v1/connect failure looks like unsupported firmware."""
        if response.status_code == 500:
            _LOGGER.error(
                "Device %s returned HTTP 500 from /api/v1/connect. This "
                "typically means the printer's firmware does not implement "
                "the legacy HTTP token API this integration relies on "
                "(seen on Artisan/J1 with newer firmware, which instead use "
                "Snapmaker's binary SACP protocol). Response: %s",
                self._host,
                response.text[:200],
            )
            self._unsupported_protocol_reason = (
                "Device rejected the legacy connect API (HTTP 500). This model "
                "or firmware version likely requires a protocol this "
                "integration does not yet support (e.g. SACP on Artisan/J1)."
            )

    def _mark_non_json_connect_response(self) -> None:
        """Record a reason when /api/v1/connect returns a non-JSON body."""
        self._unsupported_protocol_reason = (
            "Device did not return a JSON token response from the "
            "legacy connect API. This model or firmware version may "
            "require a protocol this integration does not yet support."
        )

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

    def check_reachability(self) -> bool:
        """Check if the device API port is open without attempting authentication.

        Used by the config flow for a connectivity-only probe that does NOT
        make any HTTP requests, avoiding a spurious touchscreen prompt.

        UDP discovery is attempted first to populate self._model, but its
        result does NOT gate the return value — UDP broadcast is frequently
        filtered on networks with VLANs, AP isolation, or subnet routing.
        TCP reachability of port 8080 is the authoritative check, since the
        user has already supplied an explicit IP address.

        Returns:
            True if the TCP API port is reachable, False otherwise.
        """
        self._check_online()  # best-effort: populates self._model if UDP works
        return self._check_reachable()

    def _connect_with_token(self, token: str) -> Optional[bool]:
        """Reconnect to the device using an existing known token.

        The Snapmaker requires a POST to /api/v1/connect with the saved token
        to re-establish the session before status can be polled. Without this,
        the device returns 401 on every status request even with a valid token.
        This mirrors how Luban reconnects on startup.

        Returns:
            True if the device accepted the token, False if it rejected it,
            None if the attempt failed for a transient reason (network error,
            or HTTP 403 while another client is waiting on the touchscreen).
        """
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/connect"
            response = requests.post(
                url,
                data=f"token={token}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=API_TIMEOUT,
            )
            if response.status_code == 401:
                _LOGGER.warning("Token reconnect rejected by device %s", self._host)
                return False
            if response.status_code == 403:
                self._busy_polls += 1
                if self._busy_polls >= BUSY_REAUTH_POLLS:
                    _LOGGER.warning(
                        "Device %s has refused the saved token with 403 for %d "
                        "polls in a row; treating it as rejected",
                        self._host,
                        self._busy_polls,
                    )
                    return False
            else:
                self._busy_polls = 0
            response.raise_for_status()
            try:
                data = json.loads(response.text)
                if data.get("token") == token:
                    _LOGGER.debug("Reconnected to Snapmaker using existing token")
                    return True
            except (json.JSONDecodeError, ValueError) as err:
                _LOGGER.error("Failed to parse token reconnect response: %s", err)
            _LOGGER.warning("Token reconnect rejected by device %s", self._host)
            return False
        except requests.exceptions.RequestException as err:
            _LOGGER.warning(
                "Could not reconnect to %s, will retry on the next poll: %s",
                self._host,
                err,
            )
            return None

    def _reconnect(self) -> bool:
        """Reopen the session on the saved token. Returns True on success.

        Only a device that rejects the token marks it invalid (triggering
        reauth); a transient failure just fails this poll. A successful
        reconnect clears token_invalid so the coordinator recovers.
        """
        result = self._connect_with_token(self._token)
        if result:
            self._connected = True
            self._available = True
            self._token_invalid = False
            return True
        if result is False:
            _LOGGER.warning(
                "Failed to reconnect with saved token for %s, "
                "token may have been invalidated",
                self._host,
            )
            self._token_invalid = True
        self._available = False
        self._status = "OFFLINE"
        return False

    def update(self) -> Dict[str, Any]:
        """Update device data."""
        if not self._connected:
            # Best-effort UDP discovery to populate self._model/self._status.
            # Result does NOT gate the update — UDP broadcast is frequently
            # filtered on networks with VLANs or AP isolation. TCP is authoritative.
            self._check_online()
        else:
            # Active session already established (e.g. just after generate_token()).
            # Skip UDP discovery: we know the device is there because we already
            # have a working HTTP session. Mark available so the status check
            # proceeds; _set_offline() will correct this if TCP fails.
            self._available = True

        # TCP reachability pre-check before making HTTP calls
        if not self._check_reachable():
            _LOGGER.warning(
                "Device %s API port %d not reachable",
                self._host,
                API_PORT,
            )
            self._set_offline()
            return self._data

        # TCP succeeded — device is reachable regardless of UDP outcome
        self._available = True

        if self._token:
            if self._connected and self._get_status() != 401:
                return self._data
            # No session yet (HA startup, or the device came back online), or
            # it expired between polls: the device drops an idle session after
            # 10-20 s, well inside the 30 s poll interval, and answers 401
            # until the token reconnects. Reopen it on the saved token and
            # poll again. This reuses an already-trusted token silently, with
            # no touchscreen dialog to dismiss, so it doesn't need the
            # settle-retry protection that follows a fresh handshake.
            if self._reconnect() and self._get_status() == 401:
                _LOGGER.error(
                    "Device %s still answers 401 after reconnecting with the "
                    "saved token",
                    self._host,
                )
                self._token_invalid = True
            return self._data

        # No saved token. Pairing needs the user at the touchscreen, so it only
        # happens in the config flow (generate_token()). Requesting a token
        # here would leave an approval request pending on the printer every
        # poll, which also makes it refuse other clients with 403.
        _LOGGER.error("No saved token for %s; reauthorize the integration", self._host)
        self._token_invalid = True
        self._available = False
        self._status = "OFFLINE"
        return self._data

    def _set_offline(self) -> None:
        """Set device to offline state with default values.

        Uses None for numeric values that are unknown when offline,
        allowing HA to display "unknown" rather than misleading zeros.
        """
        self._available = False
        self._status = "OFFLINE"
        self._connected = False  # Force reconnect POST when device comes back up
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

    def generate_token(
        self, max_attempts: int = 90, poll_interval: int = 2
    ) -> Optional[str]:
        """Generate a new authentication token from Snapmaker device.

        The device hands out a token on the first /api/v1/connect POST, before
        anyone has approved it. Approval is only visible on /api/v1/status,
        which answers 204 with an empty body while the touchscreen prompt is
        pending, 200 with the status JSON once the user taps Authorize, and 401
        if the token is rejected. This mirrors how Luban pairs.

        IMPORTANT: This method blocks the executor thread for up to
        (max_attempts * poll_interval) seconds. Default settings can block
        for up to 3 minutes (90 × 2s), which may impact the thread pool's
        ability to handle other tasks. Consider the thread pool size when
        calling this method.

        Args:
            max_attempts: Maximum number of status polls (default 90 = 3 minutes)
            poll_interval: Seconds to wait between status polls (default 2)

        Returns:
            Optional[str]: Authentication token if successful, None otherwise
        """
        self._unsupported_protocol_reason = None
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/connect"

            # First request to initiate connection
            _LOGGER.info("Requesting token from Snapmaker at %s", self._host)
            response = requests.post(url, timeout=API_TIMEOUT)

            # Check HTTP status before parsing response
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                _LOGGER.error(
                    "HTTP error requesting token: %s. Response: %s",
                    http_err,
                    response.text[:200],
                )
                self._classify_connect_failure(response)
                return None

            # Extract token from response
            try:
                token = json.loads(response.text).get("token")
            except (json.JSONDecodeError, ValueError) as json_err:
                _LOGGER.error(
                    "Failed to parse token response: %s. Response: %s",
                    json_err,
                    response.text[:200],
                )
                self._mark_non_json_connect_response()
                return None

            if not token:
                _LOGGER.error("No token received from Snapmaker")
                return None

            _LOGGER.info(
                "Token received, waiting for user authorization on touchscreen..."
            )

            # Poll status until the user authorizes on the touchscreen.
            # First attempt is immediate (no sleep), subsequent attempts wait poll_interval
            status_url = f"http://{self._host}:{API_PORT}/api/v1/status"
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        # Blocking sleep in executor thread - this is acceptable as it runs
                        # in a separate thread pool, not blocking the event loop
                        time.sleep(poll_interval)

                    response = requests.get(
                        status_url, params={"token": token}, timeout=API_TIMEOUT
                    )

                    if response.status_code == 401:
                        _LOGGER.error(
                            "Snapmaker at %s rejected the token (401)", self._host
                        )
                        return None

                    # 204 / empty body: the approval prompt is still on screen
                    if response.status_code == 204 or not (
                        response.text and response.text.strip()
                    ):
                        _LOGGER.debug(
                            "Awaiting touchscreen approval (attempt %d/%d)",
                            attempt + 1,
                            max_attempts,
                        )
                        continue

                    response.raise_for_status()

                    _LOGGER.info("Token approved on touchscreen")
                    self._token = token
                    self._token_invalid = False
                    # Session is now established; next update() can skip
                    # the reconnect POST and go straight to _get_status().
                    self._connected = True
                    self._settle_retries_pending = True
                    # Notify callback about new token for persistence
                    if self._on_token_update:
                        self._on_token_update(token)
                    return token

                except requests.exceptions.RequestException as req_err:
                    _LOGGER.debug(
                        "Network error on attempt %d/%d: %s",
                        attempt + 1,
                        max_attempts,
                        req_err,
                    )
                    continue

            _LOGGER.warning(
                "Token not approved after %d attempts. "
                "User may not have authorized on touchscreen. Note that the "
                "prompt only appears while the touchscreen is on its home screen.",
                max_attempts,
            )
            # Withdraw the request so the prompt doesn't linger on the screen
            try:
                requests.post(
                    f"http://{self._host}:{API_PORT}/api/v1/disconnect",
                    data={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=API_TIMEOUT,
                )
            except requests.exceptions.RequestException:
                pass
            return None

        except requests.exceptions.RequestException as req_err:
            _LOGGER.error("Network error requesting token from Snapmaker: %s", req_err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error generating token: %s", err)
            return None

    def _get_status(self) -> Optional[int]:
        """Get status from Snapmaker device.

        Returns 401 if the device no longer recognises the session, so the
        caller can reconnect; None otherwise.
        """
        try:
            url = f"http://{self._host}:{API_PORT}/api/v1/status"

            # Snapmaker 2.0-series devices can briefly return an empty body
            # while the touchscreen is dismissing the auth dialog just
            # approved during token generation. Only retry right after a
            # fresh handshake (the flag is cleared here either way) so
            # steady-state polling of a genuinely offline device isn't
            # slowed down on every 30s cycle.
            retry_on_empty = self._settle_retries_pending
            self._settle_retries_pending = False
            retry_count = STATUS_EMPTY_RETRY_COUNT if retry_on_empty else 1

            response = None
            for attempt in range(retry_count):
                response = requests.get(
                    url, params={"token": self._token}, timeout=API_TIMEOUT
                )
                if response.status_code == 401 or (
                    response.text and response.text.strip()
                ):
                    break
                if attempt < retry_count - 1:
                    _LOGGER.debug(
                        "Empty status response from %s (attempt %d/%d), retrying",
                        self._host,
                        attempt + 1,
                        retry_count,
                    )
                    time.sleep(STATUS_EMPTY_RETRY_DELAY)

            # Check for authentication errors
            if response.status_code == 401:
                _LOGGER.debug("Status answered 401: session expired for %s", self._host)
                self._connected = False  # Force a reconnect POST
                self._available = False
                self._status = "OFFLINE"
                return 401

            # Check if response is valid
            if not response.text or response.text.strip() == "":
                _LOGGER.error(
                    "Empty response from Snapmaker status API after %d attempts",
                    retry_count,
                )
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
                tool_head = TOOLHEAD_TYPE_DUAL_EXTRUDER
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

            # Persist toolhead type so it survives offline periods
            if tool_head and tool_head != "N/A":
                self._toolhead_type = tool_head

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
            # Snapmaker 2.0 firmware reports a boolean "homed" rather than a
            # "homing" axis string
            homing = data.get("homing")
            if homing is None:
                homed = data.get("homed")
                homing = "N/A" if homed is None else ("Homed" if homed else "Not homed")

            # Extract module/safety data. Snapmaker 2.0 firmware nests the
            # module flags under "moduleList" and names the emergency stop
            # "emergencyStopButton"; fall back to top-level keys otherwise.
            is_filament_out = data.get("isFilamentOut", False)
            is_door_open = data.get("isDoorOpen", False)
            modules = data.get("moduleList")
            if not isinstance(modules, dict):
                modules = {}
            has_enclosure = modules.get("enclosure", data.get("enclosure", False))
            has_rotary_module = modules.get(
                "rotaryModule", data.get("rotaryModule", False)
            )
            has_emergency_stop = modules.get(
                "emergencyStopButton", data.get("emergencyStop", False)
            )
            has_air_purifier = modules.get(
                "airPurifier", data.get("airPurifier", False)
            )

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
            # Note: 401 errors are already handled explicitly before raise_for_status()
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
