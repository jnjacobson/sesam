"""Constants for Sesam."""

import logging

DOMAIN = "sesam"
LOGGER = logging.getLogger(__package__)

FRITZ_DOMAIN = "fritz"

CONF_FRITZ_ENTRY = "fritz_entry_id"
CONF_MINUTES = "minutes"

DEFAULT_MINUTES = 5
MIN_MINUTES = 1
MAX_MINUTES = 120
