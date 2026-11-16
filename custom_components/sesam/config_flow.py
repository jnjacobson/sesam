"""Config flow for Sesam."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_FRITZ_ENTRY,
    CONF_MINUTES,
    DEFAULT_MINUTES,
    DOMAIN,
    FRITZ_DOMAIN,
    MAX_MINUTES,
    MIN_MINUTES,
)
from .door import BOX_ERRORS, Box, find_bands

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MINUTES, default=DEFAULT_MINUTES): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=MIN_MINUTES,
                    max=MAX_MINUTES,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        )
    }
)


class SesamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick the FRITZ!Box whose Wi-Fi Sesam opens."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SesamOptionsFlow:
        """Return the options flow."""
        return SesamOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the only step."""
        boxes = self.hass.config_entries.async_loaded_entries(FRITZ_DOMAIN)
        if not boxes:
            return self.async_abort(reason="no_fritz")

        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(
                user_input[CONF_FRITZ_ENTRY]
            )
            try:
                bands = await self.hass.async_add_executor_job(
                    find_bands, Box(entry.runtime_data.connection)
                )
            except BOX_ERRORS:
                errors["base"] = "cannot_connect"
            else:
                if bands:
                    return self.async_create_entry(title="Sesam", data=user_input)
                errors["base"] = "unsupported"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_FRITZ_ENTRY, default=boxes[0].entry_id
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=box.entry_id, label=box.title)
                            for box in boxes
                        ]
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class SesamOptionsFlow(OptionsFlow):
    """Set how long an opening lasts."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the only step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
