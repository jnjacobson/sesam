from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import MAIN_5, MAIN_24, FakeBox


async def test_setup_remembers_the_chosen_fritz_box(
    hass: HomeAssistant, fritz_entry: MockConfigEntry
) -> None:
    flow = await hass.config_entries.flow.async_init(
        "sesam", context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"fritz_entry_id": fritz_entry.entry_id}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"fritz_entry_id": fritz_entry.entry_id}


async def test_setup_is_refused_without_a_fritz_box(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        "sesam", context={"source": "user"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_fritz"


async def test_setup_is_refused_for_a_box_without_a_home_wifi_filter(
    hass: HomeAssistant, box: FakeBox, fritz_entry: MockConfigEntry
) -> None:
    del box.wifi[MAIN_24]
    del box.wifi[MAIN_5]
    flow = await hass.config_entries.flow.async_init(
        "sesam", context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"fritz_entry_id": fritz_entry.entry_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported"}


async def test_options_store_the_minutes_as_a_whole_number(
    hass: HomeAssistant, sesam: MockConfigEntry
) -> None:
    flow = await hass.config_entries.options.async_init(sesam.entry_id)

    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"minutes": 15.0}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert sesam.options == {"minutes": 15}
