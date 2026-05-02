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
        """Validate device is online and proceed to authorization."""
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

            # Only check if device is online via UDP - do NOT attempt token acquisition here
            snapmaker = SnapmakerDevice(host)
            try:
                await self.hass.async_add_executor_job(snapmaker._check_online)
                if snapmaker.available:
                    return await self._validate_and_authorize(
                        host, snapmaker.model or host
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

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
            snapmaker = SnapmakerDevice(host)
            try:
                # Generate token - polls until user approves on touchscreen
                token = await self.hass.async_add_executor_job(snapmaker.generate_token)

                if token:
                    # Validate token by attempting status with retry
                    # (status endpoint returns empty for a few seconds after approval)
                    test_device = SnapmakerDevice(host, token=token)
                    try:
                        success = await self.hass.async_add_executor_job(
                            test_device._get_status_with_retry
                        )
                        if test_device.token_invalid:
                            _LOGGER.error(
                                "Generated token is invalid on first use for %s.", host
                            )
                            errors["base"] = "auth_failed"
                        elif not success:
                            _LOGGER.warning(
                                "Device not available after token generation for %s.",
                                host,
                            )
                            errors["base"] = "cannot_connect"
                        else:
                            if self.source == config_entries.SOURCE_REAUTH:
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
                                    try:
                                        await self.hass.config_entries.async_reload(
                                            entry.entry_id
                                        )
                                    except Exception as reload_err:
                                        _LOGGER.error(
                                            "Failed to reload entry after reauth: %s",
                                            reload_err,
                                        )
                                return self.async_abort(reason="reauth_successful")
                            else:
                                return self.async_create_entry(
                                    title=f"Snapmaker {model}",
                                    data={
                                        CONF_HOST: host,
                                        CONF_TOKEN: token,
                                    },
                                )
                    except Exception:
                        _LOGGER.exception("Error validating new token")
                        errors["base"] = "unknown"
                else:
                    errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected exception during authorization")
                errors["base"] = "unknown"

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

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        snapmaker = SnapmakerDevice(host)
        try:
            await self.hass.async_add_executor_job(snapmaker._check_online)
            if snapmaker.available:
                return await self._validate_and_authorize(host, snapmaker.model or host)
        except Exception:
            pass

        self.context["host"] = host
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm the setup."""
        errors = {}
        host = self.context["host"]

        if user_input is not None:
            snapmaker = SnapmakerDevice(host)
            try:
                await self.hass.async_add_executor_job(snapmaker._check_online)
                if snapmaker.available:
                    return await self._validate_and_authorize(
                        host, snapmaker.model or host
                    )
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

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

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

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

            device_info = self.context.get("devices", {}).get(host, {})
            self.context["host"] = host
            self.context["model"] = device_info.get("model", host)
            return await self.async_step_authorize()

        devices = await self.hass.async_add_executor_job(SnapmakerDevice.discover)

        if not devices:
            return self.async_abort(reason="no_devices_found")

        self.context["devices"] = {device["host"]: device for device in devices}

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
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry:
            self.context["host"] = entry.data.get(CONF_HOST)
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
            snapmaker = SnapmakerDevice(host)
            try:
                await self.hass.async_add_executor_job(snapmaker._check_online)
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
