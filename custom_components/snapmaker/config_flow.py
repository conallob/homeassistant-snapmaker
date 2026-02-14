"""Config flow for Snapmaker integration."""

import logging

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import CONF_TOKEN, DOMAIN
from .snapmaker import SnapmakerDevice

_LOGGER = logging.getLogger(__name__)


class SnapmakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Snapmaker."""

    VERSION = 1

    async def _validate_and_authorize(self, host: str, model: str) -> FlowResult:
        """Validate device is online and proceed to authorization.

        Args:
            host: IP address of the device
            model: Model name of the device

        Returns:
            FlowResult for authorize step
        """
        self.context["host"] = host
        self.context["model"] = model
        return await self.async_step_authorize()

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
                result = await self.hass.async_add_executor_job(snapmaker.update)
                if snapmaker.available:
                    # Device is online, proceed to token authorization
                    return await self._validate_and_authorize(
                        host, snapmaker.model or host
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

    async def async_step_authorize(self, user_input=None) -> FlowResult:
        """Handle token authorization step."""
        errors = {}
        host = self.context.get("host")
        model = self.context.get("model", host)

        if user_input is not None:
            # User has confirmed, now generate token
            snapmaker = SnapmakerDevice(host)
            try:
                # Generate token with polling (default: 18 attempts × 10s = 3 minutes)
                token = await self.hass.async_add_executor_job(snapmaker.generate_token)

                if token:
                    # Validate the token works before persisting it
                    test_device = SnapmakerDevice(host, token=token)
                    try:
                        await self.hass.async_add_executor_job(test_device.update)
                        if test_device.token_invalid:
                            _LOGGER.error(
                                "Generated token is invalid on first use for %s. "
                                "Device may have rejected the token or requires re-approval.",
                                host,
                            )
                            errors["base"] = "auth_failed"
                        elif not test_device.available:
                            _LOGGER.warning(
                                "Device not available after token generation for %s. "
                                "Device status: %s",
                                host,
                                test_device.status,
                            )
                            errors["base"] = "cannot_connect"
                        else:
                            # Token is valid and device is accessible
                            # Check if this is a reauth flow
                            if self.source == config_entries.SOURCE_REAUTH:
                                # Update existing entry with new token
                                entry = self.hass.config_entries.async_get_entry(
                                    self.context["entry_id"]
                                )
                                if entry:
                                    self.hass.config_entries.async_update_entry(
                                        entry,
                                        data={
                                            **entry.data,
                                            CONF_TOKEN: token,
                                        },
                                    )
                                    # Attempt to reload with new token
                                    try:
                                        await self.hass.config_entries.async_reload(
                                            entry.entry_id
                                        )
                                    except Exception as reload_err:
                                        _LOGGER.error(
                                            "Failed to reload entry after reauth: %s",
                                            reload_err,
                                        )
                                        # Still return success since token was saved
                                    return self.async_abort(reason="reauth_successful")
                            else:
                                # Token successfully generated for initial setup
                                return self.async_create_entry(
                                    title=f"Snapmaker {model}",
                                    data={
                                        CONF_HOST: host,
                                        CONF_TOKEN: token,
                                    },
                                )
                    except Exception as validation_err:
                        _LOGGER.exception("Error validating new token")
                        errors["base"] = "unknown"
                else:
                    errors["base"] = "auth_failed"
            except Exception as err:
                _LOGGER.exception("Unexpected exception during authorization")
                errors["base"] = "unknown"

        # Show authorization form with instructions
        return self.async_show_form(
            step_id="authorize",
            description_placeholders={
                "host": host,
                "model": model,
            },
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
                # Device is online, proceed to token authorization
                return await self._validate_and_authorize(host, snapmaker.model or host)
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
                result = await self.hass.async_add_executor_job(snapmaker.update)
                if snapmaker.available:
                    # Device is online, proceed to token authorization
                    return await self._validate_and_authorize(
                        host, snapmaker.model or host
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
            "model": discovery_info.get("model", "Unknown")
        }

        return await self.async_step_confirm()

    async def async_step_pick_device(self, user_input=None):
        """Handle the step to pick discovered device."""
        if user_input is not None:
            host = user_input["device"]
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Get device info from context and proceed to authorize
            device_info = self.context.get("devices", {}).get(host, {})
            self.context["host"] = host
            self.context["model"] = device_info.get("model", host)
            return await self.async_step_authorize()

        # Discover devices
        devices = await self.hass.async_add_executor_job(SnapmakerDevice.discover)

        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Save discovered devices
        self.context["devices"] = {device["host"]: device for device in devices}

        # Create device selection schema
        devices_options = {
            device["host"]: f"{device['model']} ({device['host']}) - {device['status']}"
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

    async def async_step_reauth(self, entry_data=None) -> FlowResult:
        """Handle reauthentication when token expires."""
        # Get the entry being reauthenticated
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry:
            self.context["host"] = entry.data.get(CONF_HOST)
            # Use entry title for model display (format: "Snapmaker <model>")
            # Will be refreshed from device during authorize step
            title_parts = entry.title.split(" ", 1)
            self.context["model"] = (
                title_parts[1] if len(title_parts) > 1 else "Unknown"
            )
            self.context["entry_id"] = entry.entry_id

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Confirm reauthentication."""
        errors = {}
        host = self.context.get("host")

        if user_input is not None:
            # Validate device is still online
            snapmaker = SnapmakerDevice(host)
            try:
                result = await self.hass.async_add_executor_job(snapmaker.update)
                if snapmaker.available:
                    self.context["model"] = snapmaker.model or host
                    return await self.async_step_authorize()
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"host": host},
            errors=errors,
        )
