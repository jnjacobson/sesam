# sesam

> sesam (German for "sesame", as in *Sesam, öffne dich*: "open sesame")

Opens a FRITZ!Box Wi-Fi to new devices for a few minutes, from Home Assistant.

A FRITZ!Box can restrict its Wi-Fi to the devices it already knows (*WLAN > Sicherheit > WLAN-Zugang auf die bekannten WLAN-Geräte beschränken*). With that on, a new device stays out even with the right password, and letting it in means logging in to the box and switching the restriction off and on again. sesam does that with one button.

> [!WARNING]
> Not yet tested against a real FRITZ!Box. The box may restart its Wi-Fi for a moment when the restriction is switched.

## What you get

- **Button *Open*** (`button.sesam_open`): switches the restriction off and, after five minutes, back on. Pressing it again starts the five minutes anew.
- **Switch *MAC filter*** (`switch.sesam_mac_filter`): shows the restriction and switches it for good. Its attribute `closes_at` says when a running opening ends.
- **Action `sesam.open`**: like the button, with an optional `minutes` (1 to 120).

The five minutes can be changed in the integration's options.

The restriction comes back on even if Home Assistant restarts during an opening, and sesam keeps trying every minute while the box doesn't answer.

The guest network has no such restriction and is never touched.

## Setup

You need Home Assistant 2026.10 or newer with the [FRITZ!Box Tools](https://www.home-assistant.io/integrations/fritz) integration set up. Its FRITZ!Box user needs the right *FRITZ!Box Einstellungen*.

1. In Home Assistant, open *Settings > Marketplace*, choose *Add from link* and enter `https://github.com/jnjacobson/sesam`.
2. Install *Sesam*.
3. Add the integration and pick your FRITZ!Box.

sesam has no credentials of its own. It talks to the box through the connection FRITZ!Box Tools already holds, and to nothing else.

## How it works

The restriction is the `NewMACAddressControlEnabled` flag of the box's TR-064 service `WLANConfiguration`, one per Wi-Fi band. It can only be written with `SetConfig`, which wants all settings of the band at once. sesam reads them with `GetInfo`, writes them back unchanged apart from the flag, and reads again to check that the box took it. It refuses to write if `SetConfig` asks for a setting `GetInfo` didn't return.

## Development

```sh
uv run --with-requirements requirements_test.txt pytest
uvx ruff check . && uvx ruff format .
```

The tests run sesam inside Home Assistant against a fake FRITZ!Box (`tests/conftest.py`).
