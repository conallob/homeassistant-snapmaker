"""The Snapmaker 3D Printer integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, DOMAIN
from .snapmaker import SnapmakerDevice

_LOGGER = logging.getLogger(__name__)

# List of platforms to support
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Snapmaker component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Snapmaker from a config entry."""
    host = entry.data[CONF_HOST]

    # Restore persisted token if available
    saved_token = entry.data.get(CONF_TOKEN)
    snapmaker = SnapmakerDevice(host, token=saved_token)

    # Set up token persistence callback
    def _on_token_update(new_token: str) -> None:
        """Persist new token to config entry data."""
        if new_token and new_token != entry.data.get(CONF_TOKEN):
            new_data = {**entry.data, CONF_TOKEN: new_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.debug("Persisted new auth token for %s", host)

    snapmaker.set_token_update_callback(_on_token_update)

    async def async_update_data():
        """Fetch data from the Snapmaker device."""
        try:
            return await hass.async_add_executor_job(snapmaker.update)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Snapmaker: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Snapmaker {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device": snapmaker,
    }

    # Set up all platforms for this device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
