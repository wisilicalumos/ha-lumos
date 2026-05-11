"""
Lumos device capability registry.

This is the ONLY file you need to edit when adding a new device type.
Every platform (light, cover, binary_sensor, sensor) reads from here.

ONE DEVICE → MULTIPLE ENTITIES
───────────────────────────────
A single Lumos device can appear in more than one HA platform at the same time.
For example, a smart luminaire with a built-in PIR sensor will produce:
  • a Light entity        (light.office_ceiling)
  • a BinarySensor entity (binary_sensor.office_ceiling_occupancy)
  • a Sensor entity       (sensor.office_ceiling_lux)

All three share the same DeviceInfo identifiers so they are grouped
under one device card in the HA UI.  The coordinator fetches all data
in a single API call and each platform reads its own slice of the fields.

CAPABILITY FLAGS
────────────────
Light flags
  has_onoff       – can be switched on / off
  has_brightness  – intensity control (0-100)
  has_color_temp  – tunable white warm ↔ cool
  has_rgb         – full RGB colour

Cover flags
  has_open_close  – open + close commands
  has_stop        – pause / stop mid-travel
  has_position    – move to an exact position (0-100)

Sensor flags  (can coexist with light OR cover flags)
  has_occupancy   – PIR / presence → binary_sensor (occupied / clear)
  has_lux         – daylight level  → sensor (lux)

HOW TO ADD A NEW DEVICE TYPE
─────────────────────────────
1. Find the deviceType integer from a real GET /wide/1 response.
2. Add an entry to DEVICE_CAPABILITIES with the correct flags.
3. Restart Home Assistant.  New entities appear automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import logging

_LOGGER = logging.getLogger(__name__)

class LumosPlatform(Enum):
    """Primary HA domain this device's main function belongs to."""
    LIGHT   = auto()
    COVER   = auto()
    SENSOR  = auto()    # standalone sensor — no light or cover function
    UNKNOWN = auto()


@dataclass(frozen=True)
class LumosCapability:
    """Full capability declaration for one Lumos deviceType."""

    platform: LumosPlatform = LumosPlatform.UNKNOWN
    label:    str            = "Unknown Device"

    # ── Light ──────────────────────────────────────────────────────────────
    has_onoff:      bool = False
    has_brightness: bool = False
    has_color_temp: bool = False
    has_rgb:        bool = False
    has_rgbww:      bool = False

    # ── Cover ──────────────────────────────────────────────────────────────
    has_open_close: bool = False
    has_stop:       bool = False
    has_position:   bool = False

    # ── Sensors — can coexist with light OR cover flags ────────────────────
    has_occupancy:  bool = False    # PIR / presence  → binary_sensor
    has_lux:        bool = False    # daylight level   → sensor (lux)

    # Convenience properties used by setup helpers
    @property
    def is_light(self) -> bool:
        return self.platform == LumosPlatform.LIGHT

    @property
    def is_cover(self) -> bool:
        return self.platform == LumosPlatform.COVER

    @property
    def has_any_sensor(self) -> bool:
        return self.has_occupancy or self.has_lux


# ---------------------------------------------------------------------------
# Reusable preset kwargs  (combine freely with sensor dicts)
# ---------------------------------------------------------------------------

_ONOFF        = dict(platform=LumosPlatform.LIGHT, has_onoff=True)
_DIMMABLE     = dict(platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True)
_TW           = dict(platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True, has_color_temp=True)
_RGB          = dict(platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True, has_color_temp=True, has_rgb=True)
_RGBWW        = dict(platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True, has_color_temp=True, has_rgb=True, has_rgbww=True)
_PIR          = dict(has_occupancy=True)
_LUX          = dict(has_lux=True)
_PIR_LUX      = dict(has_occupancy=True, has_lux=True)
_CURTAIN_FULL  = dict(platform=LumosPlatform.COVER, has_open_close=True, has_stop=True, has_position=True)
_CURTAIN_BASIC = dict(platform=LumosPlatform.COVER, has_open_close=True, has_stop=True)


# ---------------------------------------------------------------------------
# DEVICE CAPABILITY MAP
#
# Key   = deviceType integer from GET /wide/1
# Value = LumosCapability
#
# TODO: Verify every integer against a real /wide/1 response for a physical
#       device of that type.  Adjust values as you confirm them.
# ---------------------------------------------------------------------------

DEVICE_CAPABILITIES: dict[int, LumosCapability] = {

    # ── Pure lights (no built-in sensor) ────────────────────────────────────

    1:  LumosCapability(**_ONOFF,    label="Non-Dimmable Light"),
    2:  LumosCapability(**_DIMMABLE, label="Dimmable Light"),
    3:  LumosCapability(**_TW,       label="Tunable White Light"),
    6:  LumosCapability(**_RGB,      label="RGB+W Light"),
    7:  LumosCapability(**_RGB,      label="RGB Light"),
    8:  LumosCapability(**_DIMMABLE, label="DALI Dimmable Light"),
    9:  LumosCapability(**_TW,       label="DALI Tunable White"),
    10: LumosCapability(**_RGB,      label="DALI RGB Light"),
    13: LumosCapability(**_DIMMABLE, label="0-10V Dimmable Driver"),
    14: LumosCapability(**_TW,       label="0-10V Tunable White Driver"),
    15: LumosCapability(**_ONOFF,    label="Smart Switch / Relay"),

    # ── Lights WITH built-in sensors ────────────────────────────────────────
    # These create entities on multiple HA platforms simultaneously.
    # light.py   sees has_onoff / has_brightness / has_color_temp / has_rgb
    # binary_sensor.py  sees has_occupancy
    # sensor.py         sees has_lux

    16: LumosCapability(**_DIMMABLE, **_PIR,
            label="Dimmable Light + Occupancy Sensor"),
    17: LumosCapability(**_TW,       **_PIR,
            label="Tunable White + Occupancy Sensor"),
    18: LumosCapability(**_TW,       **_PIR_LUX,
            label="Tunable White + Occupancy + Daylight Sensor"),
    19: LumosCapability(**_RGB,      **_PIR_LUX,
            label="RGB Light + Occupancy + Daylight Sensor"),
    20: LumosCapability(**_DIMMABLE, **_LUX,
            label="Dimmable Light + Daylight Sensor"),
    21: LumosCapability(**_TW,       **_LUX,
            label="Tunable White + Daylight Sensor"),

    # ── Standalone sensors (no light / cover function) ───────────────────────
    # platform=SENSOR tells light.py and cover.py to skip this device entirely.
    # binary_sensor.py and sensor.py check has_any_sensor on every device,
    # regardless of platform, so they will pick these up too.

    25: LumosCapability(
            platform=LumosPlatform.SENSOR,
            has_occupancy=True,
            label="Standalone Occupancy Sensor"),
    26: LumosCapability(
            platform=LumosPlatform.SENSOR,
            has_lux=True,
            label="Standalone Daylight / Lux Sensor"),
    27: LumosCapability(
            platform=LumosPlatform.SENSOR,
            has_occupancy=True,
            has_lux=True,
            label="Standalone Occupancy + Daylight Sensor"),

    # ── Curtain / Blind ──────────────────────────────────────────────────────

    22: LumosCapability(**_CURTAIN_FULL,  label="Motorised Curtain"),
    23: LumosCapability(**_CURTAIN_FULL,  label="Motorised Blind / Roller Shade"),
    24: LumosCapability(**_CURTAIN_BASIC, label="Curtain (Open/Close Only)"),
    1024: LumosCapability(**_DIMMABLE, label="Radiar DP5 - DALI Dimmer"),
    1021: LumosCapability(**_RGB, label="RGB CCT Light"),
    1022: LumosCapability(**_TW,       label="WCA2CS Tunable White"),
    1023: LumosCapability(**_TW,       label="CCT Tunable White"),
    1042: LumosCapability(**_TW,       label="Tunable White Light 1042"),
    

    # ── Add new types here as you discover them ──────────────────────────────
}


# ---------------------------------------------------------------------------
# Public helpers  (imported by every platform module)
# ---------------------------------------------------------------------------


_DEFAULT = LumosCapability(
    platform=LumosPlatform.UNKNOWN,
    has_onoff=True,
    has_rgb=True,
    has_color_temp=True,
    has_brightness=True,
    label="Unknown Type – defaulting to Dimmable Light",
)

def get_capability(device_type: int | str | None, device_name: str = "") -> LumosCapability:
    try:
        dtype = int(device_type)
    except (TypeError, ValueError):
        _LOGGER.warning("non-integer deviceType=%r ...", device_type)
        return _DEFAULT

    cap = DEVICE_CAPABILITIES.get(dtype)
    if cap is None:
        _LOGGER.warning("Unknown deviceType=%d (device: %s) ...", dtype,device_name)
        return _DEFAULT

    _LOGGER.debug("deviceType=%d → %s", dtype, cap.label)
    return cap


def is_light_device(device_type: int | str | None) -> bool:
    return get_capability(device_type).is_light


def is_cover_device(device_type: int | str | None) -> bool:
    return get_capability(device_type).is_cover


def needs_occupancy_entity(device_type: int | str | None) -> bool:
    """True for any device that reports presence — light, sensor, or cover."""
    return get_capability(device_type).has_occupancy


def needs_lux_entity(device_type: int | str | None) -> bool:
    """True for any device that reports a lux level — light, sensor, or cover."""
    return get_capability(device_type).has_lux


def needs_any_sensor_entity(device_type: int | str | None) -> bool:
    return get_capability(device_type).has_any_sensor
