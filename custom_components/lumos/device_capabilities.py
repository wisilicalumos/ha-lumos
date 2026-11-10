"""
Lumos device capability registry.

Maps the ``deviceType`` integer returned by GET /wide/1 to the light
features Home Assistant should expose for that device.

CAPABILITY FLAGS
────────────────
  has_onoff       – can be switched on / off
  has_brightness  – intensity control (0-100)
  has_color_temp  – tunable white warm ↔ cool
  has_rgb         – full RGB colour
  has_rgbww       – 5-channel RGB + warm + cool

Only the device types documented in the README are mapped. Any other
deviceType is skipped (no entity is created) and logged once as a warning
so it can be reported and added.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import logging

_LOGGER = logging.getLogger(__name__)


class LumosPlatform(Enum):
    """Home Assistant platform a device type belongs to."""

    LIGHT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class LumosCapability:
    """Capability declaration for one Lumos deviceType."""

    platform: LumosPlatform = LumosPlatform.UNKNOWN
    label: str = "Unknown Device"

    has_onoff: bool = False
    has_brightness: bool = False
    has_color_temp: bool = False
    has_rgb: bool = False
    has_rgbww: bool = False

    @property
    def is_light(self) -> bool:
        return self.platform == LumosPlatform.LIGHT


# ---------------------------------------------------------------------------
# Reusable preset kwargs
# ---------------------------------------------------------------------------

_DIMMABLE = dict(platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True)
_TW = dict(
    platform=LumosPlatform.LIGHT, has_onoff=True, has_brightness=True, has_color_temp=True
)
_RGB = dict(
    platform=LumosPlatform.LIGHT,
    has_onoff=True,
    has_brightness=True,
    has_color_temp=True,
    has_rgb=True,
)


# ---------------------------------------------------------------------------
# DEVICE CAPABILITY MAP
#
# Key   = deviceType integer from GET /wide/1
# Value = LumosCapability
#
# Keep this table in sync with the "Supported Devices" table in README.md.
# ---------------------------------------------------------------------------

DEVICE_CAPABILITIES: dict[int, LumosCapability] = {
    1021: LumosCapability(**_RGB,      label="RGB CCT Light"),
    1022: LumosCapability(**_TW,       label="WCA2CS Tunable White"),
    1023: LumosCapability(**_TW,       label="CCT Tunable White"),
    1024: LumosCapability(**_DIMMABLE, label="Radiar DP5 - DALI Dimmer"),
    1042: LumosCapability(**_TW,       label="Tunable White Light 1042"),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_UNKNOWN = LumosCapability(platform=LumosPlatform.UNKNOWN, label="Unsupported device")
_warned_types: set[object] = set()


def _warn_once(key: object, message: str, *args: object) -> None:
    if key in _warned_types:
        return
    _warned_types.add(key)
    _LOGGER.warning(message, *args)


def get_capability(
    device_type: int | str | None, device_name: str | None = ""
) -> LumosCapability:
    """Return the capability for a deviceType; unknown types are not exposed."""
    try:
        dtype = int(device_type)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        _warn_once(
            ("invalid", device_type),
            "Skipping Lumos device %s with non-integer deviceType=%r",
            device_name,
            device_type,
        )
        return _UNKNOWN

    cap = DEVICE_CAPABILITIES.get(dtype)
    if cap is None:
        _warn_once(
            dtype,
            "Unknown deviceType=%d (device: %s) — not supported yet, skipping. "
            "Please open an issue with the device type and name.",
            dtype,
            device_name,
        )
        return _UNKNOWN
    return cap


def is_light_device(device_type: int | str | None, device_name: str | None = "") -> bool:
    return get_capability(device_type, device_name).is_light
