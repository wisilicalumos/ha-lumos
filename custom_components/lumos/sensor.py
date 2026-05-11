"""
Lumos sensor platform — daylight / lux level.

Created for every device whose capability has has_lux=True,
regardless of whether that device is also a light, a cover, or a
standalone sensor.

Field used:  ATTR_LUX  ("lux" by default)
Unit:        lux  (float)
             (TODO: confirm exact field name from a real /wide/1 response
              for a daylight-sensor-capable device.  Alternatives:
              "luxLevel", "lightLevel", "ambientLux")
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DEVICE_ID,
    ATTR_DEVICE_MESH_ID,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_TYPE,
    ATTR_DEVICE_UUID,
    ATTR_FM_VERSION,
    ATTR_HW_VERSION,
    ATTR_LUX,
    ATTR_LUX_SETPOINT,
    ATTR_ORG_ID,
    ATTR_SW_VERSION,
    DOMAIN,
)
from .coordinator import LumosCoordinator
from .device_capabilities import get_capability, needs_lux_entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lumos lux sensor entities from a config entry."""
    coordinator: LumosCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_devices() -> None:
        new_entities = []
        for device_id, device_data in coordinator.data.items():
            if device_id in known_ids:
                continue
            dtype = device_data.get(ATTR_DEVICE_TYPE)
            if needs_lux_entity(dtype):
                known_ids.add(device_id)
                new_entities.append(LumosLuxSensor(coordinator, device_id))
        if new_entities:
            _LOGGER.info("Adding %d Lumos lux sensor entities", len(new_entities))
            async_add_entities(new_entities)

    coordinator.async_add_listener(_add_new_devices)
    _add_new_devices()


class LumosLuxSensor(CoordinatorEntity[LumosCoordinator], SensorEntity):
    """
    Daylight / ambient lux sensor for a Lumos device.

    When the parent device is also a light, this entity appears alongside
    the light entity under the same device card in the HA UI, enabling
    automations like "dim the light when daylight exceeds 500 lux".
    """

    _attr_has_entity_name  = True
    _attr_device_class     = SensorDeviceClass.ILLUMINANCE
    _attr_state_class      = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LIGHT_LUX

    def __init__(self, coordinator: LumosCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    # ------------------------------------------------------------------
    # Data helper
    # ------------------------------------------------------------------

    @property
    def _device_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._device_id, {})

    # ------------------------------------------------------------------
    # HA entity identity
    # ------------------------------------------------------------------

    @property
    def unique_id(self) -> str:
        uuid = self._device_data.get(ATTR_DEVICE_UUID, self._device_id)
        return f"lumos_lux_{uuid}"

    @property
    def name(self) -> str:
        """
        HA appends this to the parent device name because has_entity_name=True.
        Result: "Office Ceiling Illuminance".
        """
        return "Illuminance"

    @property
    def device_info(self) -> DeviceInfo:
        """
        Same identifiers as sibling light / occupancy entities so HA groups
        all entities under one device card.
        """
        data = self._device_data
        cap  = get_capability(data.get(ATTR_DEVICE_TYPE))
        return DeviceInfo(
            identifiers={(DOMAIN, str(data.get(ATTR_DEVICE_UUID, self._device_id)))},
            name=data.get(ATTR_DEVICE_NAME, f"Lumos {self._device_id}"),
            manufacturer="WiSilica",
            model=cap.label,
            sw_version=data.get(ATTR_SW_VERSION),
            hw_version=data.get(ATTR_HW_VERSION),
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """
        Ambient light level in lux.

        Reads ATTR_LUX ("lux") from coordinator data.
        TODO: Confirm the exact field name from a real /wide/1 response.
              Possible alternatives: "luxLevel", "lightLevel", "ambientLux"
        """
        raw = self._device_data.get(ATTR_LUX)
        if raw is None:
            return None
        try:
            return round(float(raw), 1)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Extra attributes
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data
        attrs: dict[str, Any] = {
            "lumos_device_id":  data.get(ATTR_DEVICE_ID),
            "lumos_mesh_id":    data.get(ATTR_DEVICE_MESH_ID),
            "lumos_org_id":     data.get(ATTR_ORG_ID),
            "lux_setpoint":     data.get(ATTR_LUX_SETPOINT),   # daylight target threshold
            "fw_version":       data.get(ATTR_FM_VERSION),
        }
        return {k: v for k, v in attrs.items() if v is not None}
