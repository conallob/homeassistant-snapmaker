"""The Snapmaker 3D Printer integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
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
    # Retrieve cached token if available
    cached_token = entry.data.get("token")

    snapmaker = SnapmakerDevice(host, token=cached_token)

    async def async_update_data():
        """Fetch data from the Snapmaker device."""
        try:
            data = await hass.async_add_executor_job(snapmaker.update)

            # Cache the token if it changed
            if snapmaker.token and snapmaker.token != entry.data.get("token"):
                new_data = dict(entry.data)
                new_data["token"] = snapmaker.token
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.debug("Cached new authentication token for %s", host)

            return data
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
