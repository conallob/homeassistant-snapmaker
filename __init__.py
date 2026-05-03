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
    _LOGGER.warning("Setting up Snapmaker for %s with token %s...", host, saved_token[:8] if saved_token else "None")
    snapmaker = SnapmakerDevice(host, token=saved_token)

    def _on_token_update(new_token: str) -> None:
        if not new_token:
            return

        def _do_update():
            if entry.entry_id not in hass.data.get(DOMAIN, {}):
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
        snapmaker._check_online()
        if not snapmaker.available:
            _LOGGER.warning("Device %s not found via UDP", host)
            return snapmaker._data

        if snapmaker.token:
            connected = snapmaker._connect_with_token(snapmaker.token)
            if not connected:
                _LOGGER.warning("Failed to reconnect with saved token for %s", host)
                snapmaker._token_invalid = True
                return snapmaker._data
        else:
            _LOGGER.warning("No token for %s", host)

        snapmaker._get_status_with_retry()
        return snapmaker._data

    async def async_update_data():
        nonlocal reauth_triggered
        _LOGGER.warning("async_update_data called for %s", host)

        try:
            result = await hass.async_add_executor_job(_update_with_reconnect)
            _LOGGER.warning("executor job done, result keys: %s", list(result.keys()) if result else None)

            async with reauth_lock:
                _LOGGER.warning("token_invalid=%s reauth_triggered=%s", snapmaker.token_invalid, reauth_triggered)
                if snapmaker.token_invalid and not reauth_triggered:
                    _LOGGER.error("Token is invalid, triggering reauth flow")
                    reauth_triggered = True
                    entry.async_start_reauth(hass)
                    raise UpdateFailed("Token authentication failed, please reauthorize")
                elif snapmaker.token_invalid:
                    raise UpdateFailed("Token authentication failed, reauth in progress")

                reauth_triggered = False

            _LOGGER.warning("async_update_data returning successfully")
            return result
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error in update: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with Snapmaker: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Snapmaker {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    _LOGGER.warning("Calling async_config_entry_first_refresh")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.warning("async_config_entry_first_refresh done, last_update_success=%s", coordinator.last_update_success)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device": snapmaker,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.warning("Platforms set up, coordinator.last_update_success=%s", coordinator.last_update_success)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
