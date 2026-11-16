from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import GUEST, MAIN_5, MAIN_24, FakeBox

SWITCH = "switch.sesam_mac_filter"
BUTTON = "button.sesam_open"
QR_CODE = "image.sesam_qr_code"


async def press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": BUTTON}, blocking=True
    )


async def let_pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **duration: int
) -> None:
    freezer.tick(timedelta(**duration))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def home_filter(box: FakeBox) -> list[bool]:
    return [box.filter_on(MAIN_24), box.filter_on(MAIN_5)]


async def test_switch_shows_the_filter_of_the_box(
    hass: HomeAssistant, sesam: MockConfigEntry
) -> None:
    assert hass.states.get(SWITCH).state == "on"


async def test_pressing_the_button_switches_the_filter_off(
    hass: HomeAssistant, box: FakeBox, sesam: MockConfigEntry
) -> None:
    await press(hass)

    assert home_filter(box) == [False, False]
    assert hass.states.get(SWITCH).state == "off"


async def test_filter_is_still_off_shortly_before_the_five_minutes_are_over(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await press(hass)

    await let_pass(hass, freezer, minutes=4, seconds=50)

    assert home_filter(box) == [False, False]


async def test_filter_is_back_on_five_minutes_after_pressing_the_button(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await press(hass)

    await let_pass(hass, freezer, minutes=5, seconds=1)

    assert home_filter(box) == [True, True]
    assert hass.states.get(SWITCH).state == "on"


async def test_switch_tells_when_the_opening_ends(
    hass: HomeAssistant, sesam: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-16 18:00:00+00:00")

    await press(hass)

    assert (
        hass.states.get(SWITCH).attributes["closes_at"] == "2026-11-16T18:05:00+00:00"
    )


async def test_button_uses_the_minutes_from_the_options(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    hass.config_entries.async_update_entry(sesam, options={"minutes": 15})
    await press(hass)

    await let_pass(hass, freezer, minutes=14)

    assert home_filter(box) == [False, False]


async def test_open_action_takes_its_own_minutes(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await hass.services.async_call("sesam", "open", {"minutes": 2}, blocking=True)

    await let_pass(hass, freezer, minutes=2, seconds=1)

    assert home_filter(box) == [True, True]


async def test_opening_never_touches_the_guest_network(
    hass: HomeAssistant, box: FakeBox, sesam: MockConfigEntry
) -> None:
    await press(hass)

    assert [service for service, _ in box.config_writes] == [MAIN_24, MAIN_5]
    assert box.filter_on(GUEST) is False


async def test_switching_off_by_hand_during_an_opening_keeps_the_filter_off(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await press(hass)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH}, blocking=True
    )

    await let_pass(hass, freezer, minutes=10)

    assert home_filter(box) == [False, False]


async def test_switching_on_by_hand_ends_the_opening(
    hass: HomeAssistant, box: FakeBox, sesam: MockConfigEntry
) -> None:
    await press(hass)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": SWITCH}, blocking=True
    )

    assert home_filter(box) == [True, True]
    assert hass.states.get(SWITCH).attributes["closes_at"] is None


async def test_opening_that_ran_out_while_home_assistant_was_down_is_closed_on_start(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await press(hass)
    await hass.config_entries.async_unload(sesam.entry_id)
    await let_pass(hass, freezer, minutes=30)

    await hass.config_entries.async_setup(sesam.entry_id)
    await let_pass(hass, freezer, seconds=1)

    assert home_filter(box) == [True, True]


async def test_filter_goes_back_on_once_an_unreachable_box_answers_again(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await press(hass)
    box.offline = True
    await let_pass(hass, freezer, minutes=5, seconds=1)
    box.offline = False

    await let_pass(hass, freezer, minutes=1, seconds=1)

    assert home_filter(box) == [True, True]


async def test_opening_that_fails_halfway_is_still_closed_after_five_minutes(
    hass: HomeAssistant,
    box: FakeBox,
    sesam: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    box.set_config_inputs.append("NewX_AVM-DE_Unbekannt")
    with pytest.raises(HomeAssistantError):
        await press(hass)
    box.set_config_inputs.remove("NewX_AVM-DE_Unbekannt")
    box.wifi[MAIN_24]["info"]["NewMACAddressControlEnabled"] = False

    await let_pass(hass, freezer, minutes=5, seconds=1)

    assert home_filter(box) == [True, True]


async def test_box_without_a_home_wifi_filter_is_not_set_up(
    hass: HomeAssistant, box: FakeBox, sesam_entry: MockConfigEntry
) -> None:
    del box.wifi[MAIN_24]
    del box.wifi[MAIN_5]

    await hass.config_entries.async_setup(sesam_entry.entry_id)

    assert hass.states.get(SWITCH) is None


async def test_qr_code_is_the_one_of_the_home_wifi(
    hass: HomeAssistant, sesam: MockConfigEntry, hass_client: ClientSessionGenerator
) -> None:
    client = await hass_client()

    response = await client.get(f"/api/image_proxy/{QR_CODE}")

    assert response.status == 200
    assert await response.read() == "PNG of Kükennetz".encode()
