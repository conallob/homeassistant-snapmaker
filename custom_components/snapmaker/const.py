"""Constants for the Snapmaker integration."""

DOMAIN = "snapmaker"

# Configuration constants
CONF_TOKEN = "token"

# Default values
DEFAULT_NAME = "Snapmaker"

# Configuration keys
CONF_TOKEN = "token"

# Toolhead type display names
TOOLHEAD_TYPE_EXTRUDER = "Extruder"
TOOLHEAD_TYPE_DUAL_EXTRUDER = "Dual Extruder"
TOOLHEAD_TYPE_CNC = "CNC"
TOOLHEAD_TYPE_LASER = "Laser"

# Map raw API toolhead identifiers to display names
TOOLHEAD_MAP = {
    "TOOLHEAD_3DPRINTING_1": TOOLHEAD_TYPE_EXTRUDER,
    "TOOLHEAD_3DPRINTING_2": TOOLHEAD_TYPE_DUAL_EXTRUDER,
    "TOOLHEAD_CNC_1": TOOLHEAD_TYPE_CNC,
    "TOOLHEAD_LASER_1": TOOLHEAD_TYPE_LASER,
    "TOOLHEAD_LASER_2": TOOLHEAD_TYPE_LASER,
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
