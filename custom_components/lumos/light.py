from __future__ import annotations
import asyncio
import logging
from typing import Any
from homeassistant.components.light import (
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import (
    ATTR_COOL, ATTR_DEVICE_ID, ATTR_DEVICE_MESH_ID, ATTR_DEVICE_NAME,
    ATTR_DEVICE_STATUS, ATTR_DEVICE_TYPE, ATTR_DEVICE_UUID, ATTR_FM_VERSION,
    ATTR_HW_VERSION, ATTR_INTENSITY, ATTR_ORG_ID, ATTR_RGB, ATTR_SW_VERSION,
    ATTR_WARM, DOMAIN,
)
from .coordinator import LumosCoordinator
from .device_capabilities import LumosCapability, get_capability, is_light_device

_LOGGER = logging.getLogger(__name__)

_BRIGHTNESS = "brightness"
_COLOR_TEMP = "color_temp"
_COLOR_TEMP_K = "color_temp_kelvin"
_RGB_COLOR = "rgb_color"

_LUMOS_WARM_K = 1800
_LUMOS_COOL_K = 6500
_MIRED_WARM = int(1_000_000 / _LUMOS_WARM_K)
_MIRED_COOL = int(1_000_000 / _LUMOS_COOL_K)

def _lumos_cool_from_mireds(mireds: int) -> int:
    mireds = max(_MIRED_COOL, min(_MIRED_WARM, mireds))
    ratio = (_MIRED_WARM - mireds) / (_MIRED_WARM - _MIRED_COOL)
    return round(ratio * 100)

def _mireds_from_lumos_cool(cool: int) -> int:
    cool = max(0, min(100, cool))
    return round(_MIRED_WARM - (cool / 100.0) * (_MIRED_WARM - _MIRED_COOL))

def _parse_rgb(rgb_str: str | None) -> tuple[int, int, int] | None:
    if not rgb_str:
        return None
    try:
        r, g, b = (int(v.strip()) for v in rgb_str.split(","))
        return (r, g, b)
    except Exception:
        return None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LumosCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()
    def _add_new_devices() -> None:
        new_entities = []
        for device_id, device_data in coordinator.data.items():
            if device_id in known_ids:
                continue
            if is_light_device(device_data.get(ATTR_DEVICE_TYPE)):
                known_ids.add(device_id)
                new_entities.append(LumosLight(coordinator, device_id))
        if new_entities:
            async_add_entities(new_entities)
    coordinator.async_add_listener(_add_new_devices)
    _add_new_devices()

class LumosLight(CoordinatorEntity[LumosCoordinator], LightEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LumosCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._optimistic_on: bool | None = None
        self._optimistic_rgb: tuple[int,int,int] | None = None
        self._optimistic_rgbww: tuple[int,int,int,int,int] | None = None
        self._optimistic_cool: int | None = None
        self._optimistic_brightness: int | None = None

    @property
    def _cap(self) -> LumosCapability:
        return get_capability(self._device_data.get(ATTR_DEVICE_TYPE), self._device_data.get(ATTR_DEVICE_NAME))

    @property
    def _device_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def unique_id(self) -> str:
        return f"lumos_{self._device_data.get(ATTR_DEVICE_ID, self._device_id)}"

    @property
    def name(self) -> str:
        return self._device_data.get(ATTR_DEVICE_NAME)

    @property
    def device_info(self) -> DeviceInfo:
        data = self._device_data
        return DeviceInfo(
            identifiers={(DOMAIN, str(data.get(ATTR_DEVICE_ID)))},
            name=data.get(ATTR_DEVICE_NAME),
            manufacturer="WiSilica",
            model=self._cap.label,
        )
    @property
    def color_mode(self) -> ColorMode:
        cap = self._cap
        if cap.has_rgbww:
            return ColorMode.RGBWW
        if self._optimistic_cool is not None and cap.has_color_temp:
            return ColorMode.COLOR_TEMP
        if cap.has_rgb and self.rgb_color:
            return ColorMode.RGB
        if cap.has_color_temp and self.color_temp:
            return ColorMode.COLOR_TEMP
        if cap.has_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        cap = self._cap
        modes: set[ColorMode] = set()
        if cap.has_rgbww:
            modes.add(ColorMode.RGBWW)
        else:
            if cap.has_rgb:
                modes.add(ColorMode.RGB)
            if cap.has_color_temp:
                modes.add(ColorMode.COLOR_TEMP)
            if cap.has_brightness and not modes:
                modes.add(ColorMode.BRIGHTNESS)
        return modes or {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        if self._optimistic_on is not None:
            return self._optimistic_on
        raw = self._device_data.get(ATTR_DEVICE_STATUS)
        return str(raw) in ("1", "true", "on", "True")

    @property
    def brightness(self) -> int | None:
        if not self._cap.has_brightness:
            return None
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
        return round(int(self._device_data.get(ATTR_INTENSITY, 0)) * 255 / 100)

    @property
    def color_temp(self) -> int | None:
        if not self._cap.has_color_temp or self._cap.has_rgbww:
            return None
        return _mireds_from_lumos_cool(int(self._device_data.get(ATTR_COOL, 0)))

    @property
    def rgb_color(self) -> tuple[int,int,int] | None:
        if not self._cap.has_rgb or self._cap.has_rgbww:
            return None
        if self._optimistic_rgb is not None:
            return self._optimistic_rgb
        parsed = _parse_rgb(self._device_data.get(ATTR_RGB))
        if parsed is None or parsed == (0, 0, 0):
            return (255, 255, 255)
        return parsed

    @property
    def rgbww_color(self) -> tuple[int,int,int,int,int] | None:
        if not self._cap.has_rgbww:
            return None
        if self._optimistic_rgbww is not None:
            return self._optimistic_rgbww
        parsed = _parse_rgb(self._device_data.get(ATTR_RGB))
        r, g, b = parsed if parsed else (255, 255, 255)
        warm = round(int(self._device_data.get(ATTR_WARM, 0)) * 255 / 100)
        cool = round(int(self._device_data.get(ATTR_COOL, 0)) * 255 / 100)
        return (r, g, b, warm, cool)
    @property
    def min_color_temp_kelvin(self) -> int:
        return _LUMOS_WARM_K
    @property
    def max_color_temp_kelvin(self) -> int:
        return _LUMOS_COOL_K
    @property
    def min_mireds(self):
        return _MIRED_COOL
    @property
    def max_mireds(self):
        return _MIRED_WARM

    async def async_turn_on(self, **kwargs: Any) -> None:
        api = self.coordinator.api
        dev_id = self._device_id
        org_id = self._device_data.get(ATTR_ORG_ID)
        _LOGGER.debug("turn_on kwargs: %s", kwargs)
        cur_i = int(self._device_data.get(ATTR_INTENSITY, 100))
        cur_cool = int(self._device_data.get(ATTR_COOL, 0))
        cur_warm = int(self._device_data.get(ATTR_WARM, 0))
        if self._cap.has_rgb:
            cur_rgb = self._device_data.get(ATTR_RGB, "255,255,255")
            if not cur_rgb or cur_rgb == "0,0,0": cur_rgb = "255,255,255"
        else:
            cur_rgb = "0,0,0"
        if ATTR_RGBWW_COLOR in kwargs and self._cap.has_rgbww:
            r, g, b, ww, cw = kwargs[ATTR_RGBWW_COLOR]
            warm_pct = round(ww * 100 / 255)
            cool_pct = round(cw * 100 / 255)
            await api.set_rgbww(dev_id, org_id, r, g, b, warm=warm_pct, cool=cool_pct, intensity=cur_i)
            self._optimistic_rgbww = (r, g, b, ww, cw)
        elif _RGB_COLOR in kwargs and self._cap.has_rgb:
            r, g, b = kwargs[_RGB_COLOR]
            await api.set_rgb(dev_id, org_id, r, g, b, intensity=cur_i, cool=cur_cool)
            self._optimistic_rgb = (r, g, b)
        elif (_COLOR_TEMP in kwargs or _COLOR_TEMP_K in kwargs) and self._cap.has_color_temp:
            if _COLOR_TEMP_K in kwargs:
                kelvin = kwargs[_COLOR_TEMP_K]
                kelvin = max(_LUMOS_WARM_K, min(_LUMOS_COOL_K, kelvin))
                cool = round(100 - (kelvin - _LUMOS_WARM_K) * 100 / (_LUMOS_COOL_K - _LUMOS_WARM_K))
            else:
                cool = _lumos_cool_from_mireds(kwargs[_COLOR_TEMP])
            self._optimistic_rgb = None
            await api.set_color_temp(dev_id, org_id, cool, intensity=cur_i, rgb="255,255,255")
            self._optimistic_cool = cool
        elif _BRIGHTNESS in kwargs:
            intensity = round(kwargs[_BRIGHTNESS] * 100 / 255)
            await api.set_intensity(dev_id, org_id, intensity, cool=cur_cool, rgb=cur_rgb)
            self._optimistic_brightness = kwargs[_BRIGHTNESS]
        else:
            await api.turn_on(dev_id, org_id)
        self._optimistic_on = True
        self.async_write_ha_state()
        self.hass.async_create_task(self._clear_optimistic_after(15))

    async def _clear_optimistic_after(self, delay: int = 15) -> None:
        await asyncio.sleep(delay)
        self._optimistic_rgbww = None
        self._optimistic_cool = None
        cloud_intensity = int(self._device_data.get(ATTR_INTENSITY, 100))
        if cloud_intensity < 99:
            self._optimistic_brightness = None
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.turn_off(self._device_id, self._device_data.get(ATTR_ORG_ID))
        self._optimistic_on = False
        self.async_write_ha_state()
