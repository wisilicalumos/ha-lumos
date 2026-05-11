"""Constants for the Lumos Smart Lighting integration."""

DOMAIN = "lumos"
# Config entry keys
CONF_BASE_URL = "base_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BUNDLE_ID = "bundle_id"
CONF_BUNDLE_PACKAGE = "bundle_package"

# Defaults
DEFAULT_SCAN_INTERVAL = 30          # seconds between coordinator polls
DEFAULT_BUNDLE_ID = "68d4f468bcb8"
DEFAULT_BUNDLE_PACKAGE = "com.wisilica.home"

# Lumos API status codes
API_STATUS_SUCCESS = 20001

# Device type constants (from Lumos platform)
DEVICE_TYPE_GATEWAY = 5
DEVICE_TYPE_GATEWAY2 = 4

# Attribute keys returned by Lumos /wide/1 device listing
ATTR_DEVICE_ID = "deviceId"
ATTR_DEVICE_UUID = "deviceUuid"
ATTR_PARENT_ID = "parentId"
ATTR_DEVICE_NAME = "deviceName"
ATTR_DEVICE_TYPE = "deviceType"
ATTR_DEVICE_MESH_ID = "deviceMeshId"
ATTR_ORG_ID = "organizationId"
ATTR_DEVICE_STATUS = "deviceStatus"   # on/off state from cloud
ATTR_INTENSITY = "intensity"          # brightness 0-100
ATTR_COOL = "cool"
ATTR_WARM = "warm"                    # warm/cool 0-100 (0=warm, 100=cool)
ATTR_RGB = "rgb"                      # RGB string e.g. "255,128,0"
ATTR_MAX_INTENSITY = "maxIntensity"
ATTR_SW_VERSION = "swVersion"
ATTR_HW_VERSION = "hwVersion"
ATTR_FM_VERSION = "fmVersion"
ATTR_POWER_RATING = "powerRating"
ATTR_TIMESTAMP = "timestamp"

# -------------------------------------------------------------------------
# Operations API
# Endpoint: POST {base_url}/operate
# e.g. https://lumos.wisilica.com/wiseconnect/api/public/operate
# -------------------------------------------------------------------------
OPERATIONS_ENDPOINT = "/operate"

# operationId values
OP_ID_OFF       = 500   # Turn device/group OFF
OP_ID_ON        = 501   # Turn device/group ON
OP_ID_INTENSITY = 503   # brightness only
OP_ID_CCT = 504         # colour temperature
OP_ID_RGB = 507         # RGB colour   # Set intensity / colour temp / RGB (combined state set)

# grpDvc flag: tells the API whether the target is a device or a group
GRP_DVC_DEVICE = 1   # targeting an individual device
GRP_DVC_GROUP  = 0   # targeting a group

# operationId values – curtain / blind
OP_ID_CURTAIN_OPEN     = 723   # Fully open
OP_ID_CURTAIN_CLOSE    = 724   # Fully close
OP_ID_CURTAIN_PAUSE    = 725   # Stop / pause mid-travel
OP_ID_CURTAIN_POSITION = 726   # Move to exact position (curtainPosition 0-100)

# Device type values
# TODO: Confirm DEVICE_TYPE_CURTAIN by inspecting the "deviceType" field of a
#       curtain device returned by GET /wide/1. Add further types as discovered.
DEVICE_TYPE_CURTAIN  = 22   # <-- verify this integer from a real /wide/1 response
CURTAIN_DEVICE_TYPES = {DEVICE_TYPE_CURTAIN}

# Platforms
PLATFORMS = ["light", "cover", "binary_sensor", "sensor"]

# -------------------------------------------------------------------------
# Sensor field names returned by Lumos /wide/1 for sensor-capable devices
# TODO: Confirm exact field names by inspecting a real /wide/1 response
#       for a device that has occupancy or daylight sensing.
# -------------------------------------------------------------------------
ATTR_OCCUPANCY        = "occupancyStatus"   # 0 = clear, 1 = occupied  (TODO: confirm key)
ATTR_LUX              = "lux"               # float, lux level          (TODO: confirm key)
ATTR_LUX_SETPOINT     = "luxSetpoint"       # configured daylight target (TODO: confirm key)
ATTR_PIR_SENSITIVITY  = "pirSensitivity"    # 0-100                     (TODO: confirm key)
ATTR_HOLD_TIME        = "holdTime"          # occupancy hold time in sec (TODO: confirm key)
