"""Constants for the Snapmaker integration."""

DOMAIN = "snapmaker"

# Default values
DEFAULT_NAME = "Snapmaker"

# Configuration keys
CONF_TOKEN = "token"

# Toolhead types
TOOLHEAD_MAP = {
    "TOOLHEAD_3DPRINTING_1": "Extruder",
    "TOOLHEAD_3DPRINTING_2": "Dual Extruder",
    "TOOLHEAD_CNC_1": "CNC",
    "TOOLHEAD_LASER_1": "Laser",
    "TOOLHEAD_LASER_2": "Laser",
}

# Attributes
ATTR_MODEL = "model"
ATTR_STATUS = "status"
ATTR_NOZZLE_TEMP = "nozzle_temperature"
ATTR_NOZZLE_TARGET_TEMP = "nozzle_target_temperature"
ATTR_BED_TEMP = "bed_temperature"
ATTR_BED_TARGET_TEMP = "bed_target_temperature"
ATTR_FILENAME = "filename"
ATTR_PROGRESS = "progress"
ATTR_ELAPSED_TIME = "elapsed_time"
ATTR_REMAINING_TIME = "remaining_time"
