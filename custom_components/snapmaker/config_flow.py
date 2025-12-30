"""Config flow for Snapmaker integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .snapmaker import SnapmakerDevice

_LOGGER = logging.getLogger(__name__)


class SnapmakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Snapmaker."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Check if already configured
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Validate the connection
            snapmaker = SnapmakerDevice(host)
            try:
                result = await self.hass.async_add_executor_job(
                    snapmaker.update)
                if snapmaker.available:
                    return self.async_create_entry(
                        title=f"Snapmaker {snapmaker.model or host}",
                        data=user_input,
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info):
        """Handle DHCP discovery."""
        host = discovery_info.ip

        # Check if already configured
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        # Validate the connection
        snapmaker = SnapmakerDevice(host)
        try:
            result = await self.hass.async_add_executor_job(snapmaker.update)
            if snapmaker.available:
                return self.async_create_entry(
                    title=f"Snapmaker {snapmaker.model or host}",
                    data={CONF_HOST: host},
                )
        except Exception:
            pass

        # We need user confirmation
        self.context["host"] = host
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm the setup."""
        errors = {}
        host = self.context["host"]

        if user_input is not None:
            # Validate the connection again
            snapmaker = SnapmakerDevice(host)
            try:
                result = await self.hass.async_add_executor_job(
                    snapmaker.update)
                if snapmaker.available:
                    return self.async_create_entry(
                        title=f"Snapmaker {snapmaker.model or host}",
                        data={CONF_HOST: host},
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show confirmation form
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"host": host},
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info=None):
        """Handle discovery."""
        if discovery_info is None:
            return self.async_abort(reason="not_snapmaker_device")

        host = discovery_info["host"]

        # Check if already configured
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        # Set discovered device for confirmation
        self.context["host"] = host
        self.context["title_placeholders"] = {
            "model": discovery_info.get("model", "Unknown")}

        return await self.async_step_confirm()

    async def async_step_pick_device(self, user_input=None):
        """Handle the step to pick discovered device."""
        if user_input is not None:
            host = user_input["device"]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Snapmaker {self.context.get('devices', {}).get(host, {}).get('model', host)}",
                data={CONF_HOST: host},
            )

        # Discover devices
        devices = await self.hass.async_add_executor_job(
            SnapmakerDevice.discover)

        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Save discovered devices
        self.context["devices"] = {device["host"]: device for device in devices}

        # Create device selection schema
        devices_options = {
            device[
                "host"]: f"{device['model']} ({device['host']}) - {device['status']}"
            for device in devices
        }

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(devices_options),
                }
            ),
        )

    async def async_step_menu(self, user_input=None):
        """Handle the initial menu."""
        if user_input is None:
            return self.async_show_menu(
                step_id="menu",
                menu_options=["pick_device", "user"],
            )

        return await getattr(self, f"async_step_{user_input}")()
