from typing import Final

VERSION: Final = "0.2.1"
DOMAIN: Final = "hayward_aquaconnect"
DEFAULT_NAME: Final = "Hayward AquaConnect"
DEFAULT_SCAN_INTERVAL: Final = 5
DEFAULT_COMMAND_TIMEOUT: Final = 10
DEFAULT_COMMAND_RETRIES: Final = 1
DEFAULT_BUTTON_DELAY: Final = 0.75

CONF_COMMAND_TIMEOUT = "command_timeout"
CONF_COMMAND_RETRIES = "command_retries"
CONF_BUTTON_DELAY = "button_delay"
CONF_SLOT_OVERRIDES = "slot_overrides"

MANUFACTURER = "Hayward"
MODEL = "AQ-CO-HOMENET / AquaConnect"
