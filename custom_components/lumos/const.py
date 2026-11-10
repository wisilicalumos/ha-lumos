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
# statusCode values on /login that mean "wrong username or password".
# 20017 "Invalid username or password" (returned with HTTP 200 for both a
# wrong password and an unknown user; Lumos API 2.20.7.0).
API_STATUS_LOGIN_REJECTED: frozenset[int] = frozenset({20017})
# statusCode values on any authenticated call that mean the session token
# is invalid or expired. 20038 "Invalid authorization details" (HTTP 400)
# is returned for a made-up token and for a token superseded by a newer
# login. The token is cleared and the coordinator logs in again.
API_STATUS_SESSION_REJECTED: frozenset[int] = frozenset({20038})

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

# Platforms
PLATFORMS = ["light"]
