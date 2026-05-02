"""The Snapmaker 3D Printer integration."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, DOMAIN
from .snapmaker import SnapmakerDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Snapmaker component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Snapmaker from a config entry."""
    host = entry.data[CONF_HOST]
    saved_token = entry.data.get(CONF_TOKEN)
    snapmaker = SnapmakerDevice(host, token=saved_token)

    def _on_token_update(new_token: str) -> None:
        """Persist new token to config entry data (called from executor thread)."""
        if not new_token:
            return

        def _do_update():
            if entry.entry_id not in hass.data.get(DOMAIN, {}):
                _LOGGER.debug(
                    "Entry %s already unloaded, skipping token update", entry.entry_id
                )
                return
            if new_token != entry.data.get(CONF_TOKEN):
                new_data = {**entry.data, CONF_TOKEN: new_token}
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.debug("Persisted new auth token for %s", host)

        hass.loop.call_soon_threadsafe(_do_update)

    snapmaker.set_token_update_callback(_on_token_update)

    reauth_lock = asyncio.Lock()
    reauth_triggered = False

    def _update_with_reconnect():
        """Connect with saved token then fetch status.

        The Snapmaker requires a POST to /api/v1/connect with the saved token
        to re-establish the session before status can be polled. Without this,
        the printer returns 401 on every status request even with a valid token.
        This mirrors how Luban reconnects on startup.
        """
        # Step 1: UDP discovery to confirm device is online
        snapmaker._check_online()
        if not snapmaker.available:
            return snapmaker._data

        # Step 2: Reconnect with saved token (form-encoded POST, same as Luban)
        if snapmaker.token:
            connected = snapmaker._connect_with_token(snapmaker.token)
            if not connected:
                _LOGGER.warning(
                    "Failed to reconnect with saved token for %s, "
                    "token may have been invalidated",
                    host,
                )
                snapmaker._token_invalid = True
                return snapmaker._data

        # Step 3: Fetch status (with empty-response retry for warmup)
        snapmaker._get_status_with_retry()
        return snapmaker._data

    async def async_update_data():
        """Fetch data from the Snapmaker device."""
        nonlocal reauth_triggered

        try:
            result = await hass.async_add_executor_job(_update_with_reconnect)

            async with reauth_lock:
                if snapmaker.token_invalid and not reauth_triggered:
                    _LOGGER.error("Token is invalid, triggering reauth flow")
                    reauth_triggered = True
                    entry.async_start_reauth(hass)
                    raise UpdateFailed(
                        "Token authentication failed, please reauthorize"
                    )
                elif snapmaker.token_invalid:
                    raise UpdateFailed(
                        "Token authentication failed, reauth in progress"
                    )

                reauth_triggered = False

            return result
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Snapmaker: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Snapmaker {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device": snapmaker,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
