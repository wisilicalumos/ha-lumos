"""
Lumos binary_sensor platform — occupancy / presence detection.

Created for every device whose capability has has_occupancy=True,
regardless of whether that device is also a light, a cover, or a
standalone sensor.  All entities share the coordinator's data refresh.

Field used:   ATTR_OCCUPANCY  ("occupancyStatus" by default)
Values:       1 = occupied,  0 = clear
              (TODO: confirm exact field name and value convention from
               a real /wide/1 response for an occupancy-capable device)
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    ATTR_OCCUPANCY,
    ATTR_ORG_ID,
    ATTR_PIR_SENSITIVITY,
    ATTR_HOLD_TIME,
    ATTR_SW_VERSION,
    DOMAIN,
)
from .coordinator import LumosCoordinator
from .device_capabilities import get_capability, needs_occupancy_entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lumos occupancy binary sensors from a config entry."""
    coordinator: LumosCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_devices() -> None:
        new_entities = []
        for device_id, device_data in coordinator.data.items():
            if device_id in known_ids:
                continue
            dtype = device_data.get(ATTR_DEVICE_TYPE)
            if needs_occupancy_entity(dtype):
                known_ids.add(device_id)
                new_entities.append(LumosOccupancySensor(coordinator, device_id))
        if new_entities:
            _LOGGER.info("Adding %d Lumos occupancy sensor entities", len(new_entities))
            async_add_entities(new_entities)

    coordinator.async_add_listener(_add_new_devices)
    _add_new_devices()


class LumosOccupancySensor(CoordinatorEntity[LumosCoordinator], BinarySensorEntity):
    """
    Occupancy / presence sensor for a Lumos device.

    When the parent device is also a light, this entity appears alongside
    the light entity under the same device card in the HA UI.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

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
        return f"lumos_occupancy_{uuid}"

    @property
    def name(self) -> str:
        """
        HA appends this to the parent device name automatically because
        has_entity_name=True.  The result is e.g. "Office Ceiling Occupancy".
        """
        return "Occupancy"

    @property
    def device_info(self) -> DeviceInfo:
        """
        Use the same identifiers as the sibling light / cover entity so
        that HA groups all entities under one device card.
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
    def is_on(self) -> bool | None:
        """
        True = occupied / motion detected.
        False = clear / no motion.

        Reads ATTR_OCCUPANCY ("occupancyStatus") from coordinator data.
        TODO: Confirm the exact field name and value convention once a
              real /wide/1 response for an occupancy device is available.
              Possible alternatives: "pir", "motionStatus", "presence"
        """
        raw = self._device_data.get(ATTR_OCCUPANCY)
        if raw is None:
            return None
        try:
            return int(raw) != 0
        except (TypeError, ValueError):
            return str(raw).lower() in ("1", "true", "occupied", "on", "active")

    # ------------------------------------------------------------------
    # Extra attributes
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data
        attrs: dict[str, Any] = {
            "lumos_device_id":   data.get(ATTR_DEVICE_ID),
            "lumos_mesh_id":     data.get(ATTR_DEVICE_MESH_ID),
            "lumos_org_id":      data.get(ATTR_ORG_ID),
            "pir_sensitivity":   data.get(ATTR_PIR_SENSITIVITY),
            "hold_time_seconds": data.get(ATTR_HOLD_TIME),
            "fw_version":        data.get(ATTR_FM_VERSION),
        }
        return {k: v for k, v in attrs.items() if v is not None}
