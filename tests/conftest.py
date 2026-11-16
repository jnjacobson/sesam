"""A fake FRITZ!Box and the fixtures that put it behind Sesam."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

MAIN_24 = "WLANConfiguration1"
MAIN_5 = "WLANConfiguration2"
GUEST = "WLANConfiguration3"


def _wifi(ssid: str, channel: int, ap_type: str, filter_on: bool) -> dict[str, Any]:
    return {
        "ap_type": ap_type,
        "info": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": channel,
            "NewSSID": ssid,
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": filter_on,
            "NewStandard": "ax",
            "NewBSSID": "3C:A6:2F:00:00:01",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
            "NewX_AVM-DE_FrequencyBand": "2400" if channel < 15 else "5000",
            "NewX_AVM-DE_WLANGlobalEnable": True,
        },
    }


class FakeBox:
    """Stands in for door.Box: two home bands with the filter on, one guest network."""

    def __init__(self) -> None:
        self.wifi = {
            MAIN_24: _wifi("Kükennetz", 6, "normal", filter_on=True),
            MAIN_5: _wifi("Kükennetz", 44, "normal", filter_on=True),
            GUEST: _wifi("Kükennetz Gäste", 6, "guest", filter_on=False),
        }
        self.set_config_inputs = [
            "NewMaxBitRate",
            "NewChannel",
            "NewSSID",
            "NewBeaconType",
            "NewMACAddressControlEnabled",
            "NewBasicEncryptionModes",
            "NewBasicAuthenticationMode",
        ]
        self.config_writes: list[tuple[str, dict[str, Any]]] = []
        self.offline = False
        self.ignores_writes = False
        self.one_write_switches_all_bands = False

    def filter_on(self, service: str) -> bool:
        return self.wifi[service]["info"]["NewMACAddressControlEnabled"]

    def wifi_services(self) -> list[str]:
        return sorted(self.wifi)

    def inputs(self, service: str, action: str) -> list[str]:
        assert action == "SetConfig"
        return list(self.set_config_inputs)

    def call(
        self, service: str, action: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.offline:
            raise OSError("No route to host")
        wifi = self.wifi[service]
        if action == "GetInfo":
            return dict(wifi["info"])
        if action == "X_AVM-DE_GetWLANExtInfo":
            return {"NewX_AVM-DE_APEnabled": "1", "NewX_AVM-DE_APType": wifi["ap_type"]}
        if action == "GetChannelInfo":
            return {
                "NewChannel": wifi["info"]["NewChannel"],
                "NewPossibleChannels": "1,2,3,4,5,6,7,8,9,10,11,12,13",
                "NewX_AVM-DE_AutoChannelEnabled": True,
                "NewX_AVM-DE_FrequencyBand": wifi["info"]["NewX_AVM-DE_FrequencyBand"],
            }
        if action == "SetConfig":
            self.config_writes.append((service, dict(arguments or {})))
            if not self.ignores_writes:
                targets = (
                    [name for name, w in self.wifi.items() if w["ap_type"] == "normal"]
                    if self.one_write_switches_all_bands
                    else [service]
                )
                for name in targets:
                    self.wifi[name]["info"]["NewMACAddressControlEnabled"] = bool(
                        arguments["NewMACAddressControlEnabled"]
                    )
            return {}
        raise AssertionError(f"unexpected action {action}")


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None, hass_storage: dict) -> None:
    """Load Sesam from custom_components and keep storage in memory."""


@pytest.fixture
def box() -> FakeBox:
    return FakeBox()


@pytest.fixture
def fritz_entry(hass: HomeAssistant, box: FakeBox):
    """A loaded FRITZ!Box Tools entry whose connection leads to the fake box."""
    entry = MockConfigEntry(domain="fritz", title="FRITZ!Box 6690 Cable")
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(connection=object())
    entry.mock_state(hass, ConfigEntryState.LOADED)
    with (
        patch("custom_components.sesam.coordinator.Box", return_value=box),
        patch("custom_components.sesam.config_flow.Box", return_value=box),
    ):
        yield entry
    # Nothing of the real fritz integration was set up, so there is nothing to unload.
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)


@pytest.fixture
def sesam_entry(hass: HomeAssistant, fritz_entry: MockConfigEntry) -> MockConfigEntry:
    """Sesam's own entry, not set up yet."""
    entry = MockConfigEntry(
        domain="sesam", title="Sesam", data={"fritz_entry_id": fritz_entry.entry_id}
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def sesam(hass: HomeAssistant, sesam_entry: MockConfigEntry) -> MockConfigEntry:
    """Sesam set up against the fake box."""
    assert await hass.config_entries.async_setup(sesam_entry.entry_id)
    await hass.async_block_till_done()
    return sesam_entry
