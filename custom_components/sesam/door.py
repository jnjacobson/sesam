"""Read and write the FRITZ!Box Wi-Fi MAC filter over TR-064.

Everything here blocks on network calls and has to run in the executor.
"""

from __future__ import annotations

import time
from typing import Any

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzwlan import FritzWLAN

from .const import LOGGER

FILTER_KEY = "NewMACAddressControlEnabled"
AUTO_CHANNEL_KEY = "NewX_AVM-DE_AutoChannelEnabled"

# The box can restart its Wi-Fi after a write, so the new value may take a moment.
SETTLE_ATTEMPTS = 5
SETTLE_PAUSE = 2

BOX_ERRORS = (FritzConnectionException, OSError)


class FilterUnsupported(Exception):
    """The box does not offer the MAC filter the way this module needs it."""


class FilterNotApplied(Exception):
    """The box accepted the write but the filter did not change."""


class Box:
    """The part of a FRITZ!Box's TR-064 interface that Sesam uses."""

    def __init__(self, conn: FritzConnection) -> None:
        """Wrap the connection of the fritz integration."""
        self._conn = conn

    def wifi_services(self) -> list[str]:
        """Return the names of the Wi-Fi services, guest network included."""
        return sorted(
            name for name in self._conn.services if name.startswith("WLANConfiguration")
        )

    def call(
        self, service: str, action: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an action and return what the box answers."""
        # The fritz integration caches every Get* call until its next poll.
        # Calling the base class skips that cache, so a read right after a
        # write is fresh.
        return FritzConnection.call_action(
            self._conn, service, action, arguments=arguments
        )

    def qr_code(self, service: str) -> bytes:
        """Return a PNG of the QR code that lets a phone join this Wi-Fi."""
        number = int(service.removeprefix("WLANConfiguration"))
        wifi = FritzWLAN(fc=self._conn, service=number)
        return wifi.get_wifi_qr_code("png", border=2).getvalue()

    def inputs(self, service: str, action: str) -> list[str]:
        """Return the names of the arguments an action takes."""
        arguments = self._conn.services[service].actions[action].arguments
        return [name for name, arg in arguments.items() if arg.direction == "in"]


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true")
    return bool(value)


def find_bands(box: Box) -> list[str]:
    """Return the home network's Wi-Fi services, leaving out the guest network."""
    bands = []
    for service in box.wifi_services():
        try:
            ap_type = box.call(service, "X_AVM-DE_GetWLANExtInfo").get(
                "NewX_AVM-DE_APType"
            )
            info = box.call(service, "GetInfo")
        except (FritzServiceError, FritzActionError):
            continue
        # A service that doesn't say what it is gets skipped rather than written to.
        if ap_type in (None, "guest") or FILTER_KEY not in info:
            continue
        bands.append(service)
    return bands


def read_filter(box: Box, bands: list[str]) -> bool:
    """Return whether the MAC filter is on for every band."""
    return all(_as_bool(box.call(band, "GetInfo")[FILTER_KEY]) for band in bands)


def write_filter(box: Box, bands: list[str], enabled: bool) -> None:
    """Switch the MAC filter and check that the box took it."""
    for band in bands:
        # Read per band: one write may already have switched the others.
        info = box.call(band, "GetInfo")
        if _as_bool(info[FILTER_KEY]) == enabled:
            continue
        auto_channel = box.call(band, "GetChannelInfo").get(AUTO_CHANNEL_KEY)
        box.call(band, "SetConfig", _config_arguments(box, band, info, enabled))
        _settle(box, [band], enabled)
        auto_channel_now = box.call(band, "GetChannelInfo").get(AUTO_CHANNEL_KEY)
        if auto_channel_now != auto_channel:
            LOGGER.warning(
                "%s: automatic channel selection changed from %s to %s while "
                "switching the MAC filter",
                band,
                auto_channel,
                auto_channel_now,
            )
        else:
            LOGGER.debug("%s: automatic channel selection still %s", band, auto_channel)
    _settle(box, bands, enabled)


def _config_arguments(
    box: Box, band: str, info: dict[str, Any], enabled: bool
) -> dict[str, Any]:
    # SetConfig has no "filter only" form: it wants every setting, so the
    # current ones are written back unchanged.
    names = box.inputs(band, "SetConfig")
    if FILTER_KEY not in names:
        raise FilterUnsupported(f"{band} SetConfig has no {FILTER_KEY}")
    arguments: dict[str, Any] = {}
    for name in names:
        if name == FILTER_KEY:
            value = enabled
        elif name in info:
            value = info[name]
        else:
            raise FilterUnsupported(
                f"{band} SetConfig wants {name}, which GetInfo doesn't return"
            )
        arguments[name] = int(value) if isinstance(value, bool) else value
    return arguments


def _settle(box: Box, bands: list[str], enabled: bool) -> None:
    for attempt in range(SETTLE_ATTEMPTS):
        if attempt:
            time.sleep(SETTLE_PAUSE)
        try:
            if read_filter(box, bands) == enabled:
                return
        except BOX_ERRORS as err:
            LOGGER.debug("Box not answering yet after the write: %s", err)
    raise FilterNotApplied(
        f"MAC filter is not {'on' if enabled else 'off'} after writing it"
    )
