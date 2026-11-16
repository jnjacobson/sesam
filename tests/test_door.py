from __future__ import annotations

import pytest

from custom_components.sesam import door
from custom_components.sesam.door import (
    FilterNotApplied,
    FilterUnsupported,
    find_bands,
    read_filter,
    write_filter,
)

from .conftest import GUEST, MAIN_5, MAIN_24, FakeBox

HOME = [MAIN_24, MAIN_5]


def test_guest_network_is_not_a_band_of_the_home_network(box: FakeBox) -> None:
    assert find_bands(box) == [MAIN_24, MAIN_5]


def test_service_that_does_not_say_what_it_is_gets_left_out(box: FakeBox) -> None:
    box.wifi[MAIN_5]["ap_type"] = None

    assert find_bands(box) == [MAIN_24]


def test_filter_counts_as_off_when_one_band_has_it_off(box: FakeBox) -> None:
    box.wifi[MAIN_5]["info"]["NewMACAddressControlEnabled"] = False

    assert read_filter(box, HOME) is False


def test_switching_off_writes_each_band_with_its_other_settings_unchanged(
    box: FakeBox,
) -> None:
    write_filter(box, HOME, False)

    assert box.config_writes == [
        (
            MAIN_24,
            {
                "NewMaxBitRate": "Auto",
                "NewChannel": 6,
                "NewSSID": "Kükennetz",
                "NewBeaconType": "11iandWPA3",
                "NewMACAddressControlEnabled": 0,
                "NewBasicEncryptionModes": "None",
                "NewBasicAuthenticationMode": "None",
            },
        ),
        (
            MAIN_5,
            {
                "NewMaxBitRate": "Auto",
                "NewChannel": 44,
                "NewSSID": "Kükennetz",
                "NewBeaconType": "11iandWPA3",
                "NewMACAddressControlEnabled": 0,
                "NewBasicEncryptionModes": "None",
                "NewBasicAuthenticationMode": "None",
            },
        ),
    ]


def test_switching_on_leaves_the_guest_network_without_filter(box: FakeBox) -> None:
    box.wifi[MAIN_24]["info"]["NewMACAddressControlEnabled"] = False
    box.wifi[MAIN_5]["info"]["NewMACAddressControlEnabled"] = False

    write_filter(box, find_bands(box), True)

    assert box.filter_on(GUEST) is False


def test_box_that_switches_all_bands_with_one_write_is_written_once(
    box: FakeBox,
) -> None:
    box.one_write_switches_all_bands = True

    write_filter(box, HOME, False)

    assert [service for service, _ in box.config_writes] == [MAIN_24]


def test_filter_that_is_already_off_is_not_written(box: FakeBox) -> None:
    box.wifi[MAIN_24]["info"]["NewMACAddressControlEnabled"] = False
    box.wifi[MAIN_5]["info"]["NewMACAddressControlEnabled"] = False

    write_filter(box, HOME, False)

    assert box.config_writes == []


def test_write_the_box_ignores_is_reported(
    box: FakeBox, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(door.time, "sleep", lambda seconds: None)
    box.ignores_writes = True

    with pytest.raises(FilterNotApplied):
        write_filter(box, HOME, False)


def test_setting_the_box_wants_but_does_not_report_stops_the_write(
    box: FakeBox,
) -> None:
    box.set_config_inputs.append("NewX_AVM-DE_Unbekannt")

    with pytest.raises(FilterUnsupported):
        write_filter(box, HOME, False)

    assert box.config_writes == []
