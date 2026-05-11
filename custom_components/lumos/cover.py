"""
Lumos cover platform for Home Assistant.

Handles curtain and blind devices from the Lumos cloud.

Each device whose deviceType is in CURTAIN_DEVICE_TYPES becomes a
LumosCover entity.  The platform supports:

  Operation        operationId   HA action
  ───────────────────────────────────────────────────
  Fully open          723        open_cover()
  Fully close         724        close_cover()
  Stop mid-travel     725        stop_cover()
  Set position        726        set_cover_position(position=N)

Position scale: both Lumos and HA use 0 (closed) – 100 (open), so no
conversion is needed.

Device type detection:
  The const CURTAIN_DEVICE_TYPES contains the known curtain deviceType
  integer(s).  If a new curtain variant is discovered, add its type
  code to that set in const.py.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .device_capabilities import get_capability, is_cover_device
from .const import (
    ATTR_COOL,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_MESH_ID,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_STATUS,
    ATTR_DEVICE_TYPE,
    ATTR_DEVICE_UUID,
    ATTR_FM_VERSION,
    ATTR_HW_VERSION,
    ATTR_ORG_ID,
    ATTR_SW_VERSION,
    DOMAIN,
)
from .coordinator import LumosCoordinator

_LOGGER = logging.getLogger(__name__)

# curtainPosition field name as returned by the Lumos /wide/1 device listing
_ATTR_CURTAIN_POSITION = "curtainPosition"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lumos cover entities from a config entry."""
    coordinator: LumosCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[str] = set()

    def _add_new_devices() -> None:
        new_entities = []
        for device_id, device_data in coordinator.data.items():
            if device_id in known_ids:
                continue
            try:
                dtype = int(device_data.get(ATTR_DEVICE_TYPE, -1))
            except (TypeError, ValueError):
                dtype = -1

            if is_cover_device(dtype):
                known_ids.add(device_id)
                new_entities.append(LumosCover(coordinator, device_id))

        if new_entities:
            _LOGGER.info("Adding %d new Lumos cover entities", len(new_entities))
            async_add_entities(new_entities)

    coordinator.async_add_listener(_add_new_devices)
    _add_new_devices()


class LumosCover(CoordinatorEntity[LumosCoordinator], CoverEntity):
    """
    Represents a single Lumos curtain or blind device.

    State is read from coordinator.data[device_id].
    Commands are sent through coordinator.api (LumosApi).
    """

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator: LumosCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    # ------------------------------------------------------------------
    # Coordinator data helper
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
        return f"lumos_cover_{uuid}"

    @property
    def name(self) -> str:
        return self._device_data.get(ATTR_DEVICE_NAME, f"Lumos Curtain {self._device_id}")

    @property
    def device_info(self) -> DeviceInfo:
        data = self._device_data
        return DeviceInfo(
            identifiers={(DOMAIN, str(data.get(ATTR_DEVICE_UUID, self._device_id)))},
            name=data.get(ATTR_DEVICE_NAME, f"Lumos Curtain {self._device_id}"),
            manufacturer="WiSilica",
            model=get_capability(data.get(ATTR_DEVICE_TYPE)).label,
            sw_version=data.get(ATTR_SW_VERSION),
            hw_version=data.get(ATTR_HW_VERSION),
        )

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position: 0 = fully closed, 100 = fully open.

        Lumos and HA both use the same 0-100 scale for curtainPosition,
        so the value is returned as-is from the device data.
        """
        try:
            return int(self._device_data[_ATTR_CURTAIN_POSITION])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def is_closed(self) -> bool | None:
        """Return True when the curtain is fully closed (position == 0)."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    @property
    def is_opening(self) -> bool:
        """
        HA calls this to show the "opening" animation.

        Lumos does not push real-time travel state, so we cannot know
        whether the curtain is currently travelling.  Returns False to
        avoid showing a stale "opening" state.
        """
        return False

    @property
    def is_closing(self) -> bool:
        """Same reasoning as is_opening – always False for cloud-polling."""
        return False

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Fully open the curtain  (operationId=723)."""
        api = self.coordinator.api
        device_id = self._device_id
        org_id = self._device_data.get(ATTR_ORG_ID, api.root_org_id)
        await api.curtain_open(device_id, org_id)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close the curtain  (operationId=724)."""
        api = self.coordinator.api
        device_id = self._device_id
        org_id = self._device_data.get(ATTR_ORG_ID, api.root_org_id)
        await api.curtain_close(device_id, org_id)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the curtain mid-travel  (operationId=725)."""
        api = self.coordinator.api
        device_id = self._device_id
        org_id = self._device_data.get(ATTR_ORG_ID, api.root_org_id)
        await api.curtain_pause(device_id, org_id)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """
        Move curtain to a specific position  (operationId=726).

        HA passes position as 0-100 in kwargs[ATTR_POSITION].
        Lumos curtainPosition is also 0-100, so no conversion is needed.
        """
        position: int = kwargs[ATTR_POSITION]
        api = self.coordinator.api
        device_id = self._device_id
        org_id = self._device_data.get(ATTR_ORG_ID, api.root_org_id)
        await api.curtain_set_position(device_id, org_id, position)
        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------------------
    # Extra state attributes
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data
        attrs: dict[str, Any] = {
            "lumos_device_id": data.get(ATTR_DEVICE_ID),
            "lumos_mesh_id": data.get(ATTR_DEVICE_MESH_ID),
            "lumos_device_type": data.get(ATTR_DEVICE_TYPE),
            "lumos_org_id": data.get(ATTR_ORG_ID),
            "fw_version": data.get(ATTR_FM_VERSION),
        }
        return {k: v for k, v in attrs.items() if v is not None}
