"""
Async API client for the Lumos Smart Lighting cloud platform.

Authentication flow (derived from cloud_syncer_cloud.py):
  1. POST /app-registration  →  obtain appId
  2. POST /login             →  obtain token, rootOrgId, phoneLongId (cloudSourceId)
  3. All subsequent calls carry headers: token, organizationId, phoneId

Device data fields available from GET /wide/1:
  deviceId, deviceUuid, deviceName, deviceType, deviceMeshId, organizationId,
  deviceStatus, intensity, cool, rgb, maxIntensity, turnOnIntensity, powerRating,
  swVersion, hwVersion, fmVersion, timestamp, groupAssociationDetails
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import aiohttp

from .const import (
    API_STATUS_LOGIN_REJECTED,
    API_STATUS_SESSION_REJECTED,
    GRP_DVC_DEVICE,
    OPERATIONS_ENDPOINT,
    OP_ID_OFF,
    OP_ID_ON,
    OP_ID_INTENSITY,
    OP_ID_CCT,
    OP_ID_RGB,
)

_LOGGER = logging.getLogger(__name__)

PAGE_SIZE = 100
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


def _status_code(data: Any) -> int | None:
    """Return the Lumos statusCode from a response body, if present."""
    if not isinstance(data, dict):
        return None
    status = data.get("Response", {}).get("Status") if "Response" in data else data
    try:
        return int(status["statusCode"])
    except (KeyError, TypeError, ValueError):
        return None


class LumosApiError(Exception):
    """Generic Lumos API error."""


class LumosAuthError(LumosApiError):
    """Raised when authentication fails."""


class LumosApi:
    """Async client for the Lumos cloud API."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        bundle_id: str,
        bundle_package: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        # Normalise: accept both short (https://lumos.wisilica.com) and full URL
        _base = base_url.rstrip("/")
        if not _base.endswith("/api/public"):
            _base = _base.rstrip("/") + "/wiseconnect/api/public"
        self.base_url = _base
        self.username = username
        self._password = password
        self.bundle_id = bundle_id
        self.bundle_package = bundle_package

        # Populated after successful login
        self.token: str | None = None
        self.app_id: int = 0
        self.root_org_id: int = 0
        self.cloud_source_id: int = 0   # phoneLongId → used as "phoneId" header

        # Use a stable device identifier based on host MAC address
        self._device_uid = hex(uuid.getnode()).replace("0x", "").lower()

        self._session = session
        self._owns_session = session is None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session if we created it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Headers included in all authenticated requests."""
        base = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"ha-lumos-{self._device_uid}",
        }
        if self.token:
            base["token"] = self.token
            base["organizationId"] = str(self.root_org_id)
            base["phoneId"] = str(self.cloud_source_id)
        return base


    def _check_status(
        self,
        res: dict,
        context: str = "",
        *,
        auth_codes: frozenset[int] = frozenset(),
    ) -> None:
        """
        Raise if the response does not indicate success.

        Lumos returns 5-digit codes; 2xxxx codes are success variants,
        except the rejection codes checked first (20017 = invalid
        username or password).

        Codes in ``auth_codes`` (and the session-rejected codes) raise
        LumosAuthError; every other failure raises LumosApiError.
        """
        try:
            code = int(res["Response"]["Status"]["statusCode"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LumosApiError(
                "Malformed response" + (f" ({context})" if context else "")
            ) from exc
        msg = (
            res.get("Response", {})
            .get("Status", {})
            .get("statusMessage", "Unknown error")
        )
        # Check rejection codes first: Lumos reports some failures with
        # 2xxxx codes (e.g. 20017 = invalid username or password).
        if code in API_STATUS_SESSION_REJECTED:
            self.token = None
            raise LumosAuthError(f"Lumos session rejected {code}: {msg} [{context}]")
        if code in auth_codes:
            raise LumosAuthError(f"Lumos rejected credentials {code}: {msg} [{context}]")
        if str(code).startswith("2"):
            return
        raise LumosApiError(f"Lumos API error {code}: {msg} [{context}]")

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        """
        Send one request to the Lumos cloud.

        * HTTP 401/403 clears the stored token and raises LumosAuthError,
          so the next coordinator poll performs a fresh login.
        * Every other transport problem (aiohttp.ClientError, timeouts,
          non-JSON bodies) is wrapped in LumosApiError.

        Payloads and responses are never logged: /login carries the
        password hash and returns the session token.
        """
        session = await self._get_session()
        url = self.base_url + path
        _LOGGER.debug("%s %s", method, url)
        try:
            async with session.request(
                method,
                url,
                json=payload,
                headers=self._auth_headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    self.token = None
                    raise LumosAuthError(f"HTTP {resp.status} from {path}")
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    data = None
                if resp.status >= 400:
                    # Lumos sends its statusCode as JSON on 4xx replies too
                    # (e.g. HTTP 400 + 20003), so read it before failing.
                    code = _status_code(data)
                    if code in API_STATUS_SESSION_REJECTED:
                        self.token = None
                        raise LumosAuthError(f"HTTP {resp.status} {code} from {path}")
                    raise LumosApiError(f"HTTP {resp.status} (statusCode={code}) from {path}")
        except LumosApiError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LumosApiError(f"{method} {path} failed: {err!r}") from err

        if not isinstance(data, dict):
            raise LumosApiError(f"{method} {path} returned unexpected payload type")
        _LOGGER.debug(
            "%s %s -> statusCode=%s",
            method,
            url,
            data.get("Response", {}).get("Status", {}).get("statusCode"),
        )
        return data

    async def _post(self, path: str, payload: dict) -> dict:
        return await self._request("POST", path, payload)

    async def _put(self, path: str, payload: dict) -> dict:
        return await self._request("PUT", path, payload)

    async def _get(self, path: str) -> dict:
        return await self._request("GET", path)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def register_app(self) -> int:
        """
        POST /app-registration

        Registers this HA instance as a Lumos application and obtains an appId.
        A new device token is generated each time but the MAC-based deviceId is stable.
        """
        device_token = uuid.uuid1().hex
        payload = {
            "deviceId": str(uuid.getnode()),
            "modelInfo": "homeassistant",
            "osInfo": "linux",
            "deviceToken": device_token,
            "appVersion": "1.0.0",
            "bundlePackage": self.bundle_package,
            "bundleClientId": self.bundle_id,
        }
        res = await self._post("/app-registration", payload)
        try:
            self.app_id = int(res["Response"]["Data"]["appId"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LumosApiError("App registration response missing appId") from exc

        if self.app_id <= 0:
            raise LumosApiError(f"App registration returned invalid appId={self.app_id}")

        _LOGGER.debug("App registered. appId=%d", self.app_id)
        return self.app_id

    async def login(self) -> bool:
        """
        Full authentication sequence:
          1. Register the app → obtain appId
          2. POST /login with SHA-512 hashed password → obtain token + session data

        Raises LumosAuthError when the cloud rejects the credentials and
        LumosApiError for any other failure.
        """
        self.token = None
        await self.register_app()

        pass_hash = hashlib.sha512(self._password.encode()).hexdigest()
        payload = {
            "appId": self.app_id,
            "userName": self.username,
            "userPassword": pass_hash,
        }
        res = await self._post("/login", payload)
        self._check_status(res, "login", auth_codes=API_STATUS_LOGIN_REJECTED)

        try:
            data = res["Response"]["Data"]
            token = data["token"]
            root_org_id = int(data["rootOrgId"])
            cloud_source_id = int(data["phoneLongId"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LumosApiError("Login response missing session fields") from exc
        if not token:
            raise LumosApiError("Login response contained an empty token")

        self.token = token
        self.root_org_id = root_org_id
        self.cloud_source_id = cloud_source_id

        _LOGGER.info("Lumos login successful")
        return True

    @property
    def is_logged_in(self) -> bool:
        return self.token is not None

    # ------------------------------------------------------------------
    # Device listing
    # ------------------------------------------------------------------

    async def get_devices(self) -> list[dict[str, Any]]:
        """
        Fetch all devices via paginated GET /wide/1.

        Returns a flat list of device dicts from the cloud.
        Each dict contains keys like:
          deviceId, deviceUuid, deviceName, deviceType, deviceMeshId,
          organizationId, deviceStatus, intensity, cool, rgb, powerRating,
          swVersion, hwVersion, fmVersion, timestamp, groupAssociationDetails
        """
        all_devices: list[dict] = []
        start: float = 0
        gateway_types = {4, 5}

        while True:
            path = f"/wide/1?orgId=0&start={start}&limit={PAGE_SIZE}&child=1"
            res = await self._get(path)
            self._check_status(res, "get_devices")

            resp_data = res["Response"]["Data"]
            count = int(resp_data.get("deviceCount", 0))
            details: list[dict] = resp_data.get("deviceDetails", [])

            _LOGGER.debug("get_devices page: count=%d fetched=%d", count, len(details))

            if count <= 0 or not details:
                break

            for dev in details:
                # Skip gateway devices – not controllable lights
                try:
                    dtype = int(dev.get("deviceType", -1))
                    if dtype in gateway_types:
                        continue
                except (TypeError, ValueError):
                    pass
                all_devices.append(dev)

            if len(details) < PAGE_SIZE:
                break

            # Advance start cursor to the latest timestamp seen
            try:
                start = max(float(d["timestamp"]) for d in details)
            except (KeyError, TypeError, ValueError):
                break

        _LOGGER.info("get_devices: total non-gateway devices=%d", len(all_devices))
        return all_devices

    async def get_groups(self) -> list[dict[str, Any]]:
        """
        Fetch all groups and spaces via GET /wise-group/1 (categories 1 and 2).
        Useful for area/floor grouping in HA.
        """
        all_groups: list[dict] = []
        for category in [1, 2]:
            start: float = 0
            while True:
                path = f"/wise-group/1?orgId=0&start={start}&limit={PAGE_SIZE}&category={category}"
                res = await self._get(path)
                try:
                    self._check_status(res, f"get_groups cat={category}")
                except LumosApiError:
                    break

                resp_data = res["Response"]["Data"]
                count = int(resp_data.get("groupCount", 0))
                details: list[dict] = resp_data.get("groupDetails", [])

                if count <= 0 or not details:
                    break
                all_groups.extend(details)
                if len(details) < PAGE_SIZE:
                    break
                try:
                    start = max(float(d["timestamp"]) for d in details)
                except (KeyError, TypeError, ValueError):
                    break

        return all_groups

    # ------------------------------------------------------------------
    # Device state
    # ------------------------------------------------------------------

    async def get_device_status(self, device_id: int | str) -> dict[str, Any]:
        """
        Fetch live state for a single device.

        TODO: Replace with actual Lumos single-device status endpoint once
              the Operations API docs are available.  The fallback used here
              re-fetches the full device list and finds the matching entry,
              which is correct but not efficient for large installations.
        """
        # PLACEHOLDER – use a dedicated status endpoint if one exists, e.g.:
        #   return await self._get(f"/device/status/{device_id}")
        devices = await self.get_devices()
        for dev in devices:
            if str(dev.get("deviceId")) == str(device_id):
                return dev
        raise LumosApiError(f"Device {device_id} not found in device listing")

    # ------------------------------------------------------------------
    # Device operations
    #
    # Endpoint : POST {base_url}/operate
    # e.g.       https://lumos.wisilica.com/wiseconnect/api/public/operate
    #
    # Payload fields
    # ──────────────
    #  grpDvc         – 1=device target, 0=group target
    #  grpDvcId       – cloud deviceId (or groupId when grpDvc=0)
    #  organizationId – org the device belongs to (sent as string)
    #  operationId    – 500=OFF  501=ON  503=set state (intensity/colour/RGB)
    #  intensity      – 0-100 brightness
    #  cool           – 0-100  (0=warmest ~2700K, 100=coolest ~6500K)
    #  warm           – inverse mirror; set to 0 when using cool
    #  rgb            – "R,G,B" string e.g. "255,128,0"
    #  whiteIntensity – dedicated white channel (0-100)
    #  curtainPosition– part of the standard payload; always 0 for lights
    # ------------------------------------------------------------------

    def _operate_payload(
        self,
        device_id: int | str,
        org_id: int | str,
        operation_id: int,
        *,
        intensity: int = 100,
        cool: int = 100,
        warm: int = 0,
        rgb: str = "255,255,255",
        white_intensity: int = 0,
        curtain_position: int = 0,
        grp_dvc: int = GRP_DVC_DEVICE,
    ) -> dict:
        """Build the standard /operate request payload."""
        return {
            "grpDvc": grp_dvc,
            "grpDvcId": int(device_id),
            "organizationId": str(org_id),
            "operationId": operation_id,
            "intensity": intensity,
            "cool": cool,
            "warm": warm,
            "rgb": rgb,
            "whiteIntensity": white_intensity,
            "curtainPosition": curtain_position,
        }

    async def turn_on(
        self,
        device_id: int | str,
        org_id: int | str,
        *,
        intensity: int = 100,
        cool: int = 100,
    ) -> dict:
        """
        Turn a device ON  (operationId=501).

        Sends the current intensity and cool values so the device restores
        to its last known state rather than defaulting to full brightness.
        """
        payload = self._operate_payload(
            device_id, org_id,
            OP_ID_ON,
            intensity=intensity,
            cool=cool,
            warm=0,
        )
        _LOGGER.debug("turn_on  device_id=%s org_id=%s", device_id, org_id)
        return await self._post(OPERATIONS_ENDPOINT, payload)

    async def turn_off(
        self,
        device_id: int | str,
        org_id: int | str,
    ) -> dict:
        """
        Turn a device OFF  (operationId=500).
        """
        payload = self._operate_payload(
            device_id, org_id,
            OP_ID_OFF,
        )
        _LOGGER.debug("turn_off device_id=%s org_id=%s", device_id, org_id)
        return await self._post(OPERATIONS_ENDPOINT, payload)

    async def set_intensity(
        self,
        device_id: int | str,
        org_id: int | str,
        intensity: int,
        *,
        cool: int = 100,
        rgb: str = "255,255,255",
    ) -> dict:
        """
        Set brightness level  (operationId=503).

        Args:
            device_id : Lumos cloud device ID.
            org_id    : organizationId the device belongs to.
            intensity : 0-100 (Lumos scale; HA 0-255 is converted before calling).
            cool      : Current warm/cool value — preserved so colour temp is not reset.
            rgb       : Current RGB string  — preserved so colour is not reset.
        """
        clamped = max(0, min(100, intensity))
        payload = self._operate_payload(
            device_id, org_id,
            OP_ID_INTENSITY,
            intensity=clamped,
            cool=cool,
            warm=0,
            rgb=rgb,
        )
        _LOGGER.debug("set_intensity device_id=%s intensity=%d", device_id, clamped)
        return await self._post(OPERATIONS_ENDPOINT, payload)

    async def set_color_temp(
        self,
        device_id: int | str,
        org_id: int | str,
        cool: int,
        *,
        intensity: int = 100,
        rgb: str = "255,255,255",
    ) -> dict:
        """
        Set warm/cool colour temperature  (operationId=503).

        Args:
            device_id : Lumos cloud device ID.
            org_id    : organizationId the device belongs to.
            cool      : 0 (full warm / 2700 K) → 100 (full cool / 6500 K).
                        HA mireds are converted via _lumos_warmcool_from_mireds()
                        in light.py before this is called.
            intensity : Current brightness — preserved so it is not reset.
            rgb       : Current RGB string  — preserved so colour is not reset.
        """
        clamped = max(0, min(100, cool))
        payload = self._operate_payload(
            device_id, org_id,
            OP_ID_CCT,
            intensity=intensity,
            cool=clamped,
            warm=0,
            rgb=rgb,
        )
        _LOGGER.debug("set_color_temp device_id=%s cool=%d", device_id, clamped)
        return await self._post(OPERATIONS_ENDPOINT, payload)

    async def set_rgb(
        self,
        device_id: int | str,
        org_id: int | str,
        red: int,
        green: int,
        blue: int,
        *,
        intensity: int = 100,
        cool: int = 100,
    ) -> dict:
        """
        Set RGB colour  (operationId=503).

        Args:
            device_id      : Lumos cloud device ID.
            org_id         : organizationId the device belongs to.
            red,green,blue : 0-255 each.
            intensity      : Current brightness — preserved so it is not reset.
            cool           : Current warm/cool  — preserved so it is not reset.

        The Lumos API accepts RGB as a comma-separated string: "R,G,B"
        (confirmed from device listing and schedule payload observations).
        """
        r, g, b = (max(0, min(255, v)) for v in (red, green, blue))
        rgb_str = f"{r},{g},{b}"
        payload = self._operate_payload(
            device_id, org_id,
            OP_ID_RGB,
            intensity=intensity,
            cool=cool,
            warm=0,
            rgb=rgb_str,
        )
        _LOGGER.debug("set_rgb device_id=%s rgb=%s", device_id, rgb_str)
        return await self._post(OPERATIONS_ENDPOINT, payload)

    async def set_rgbww(self, device_id, org_id, red, green, blue, *, warm=0, cool=0, intensity=100) -> dict:
        """Set 5-channel RGBWW (operationId=507)."""
        r, g, b = (max(0, min(255, v)) for v in (red, green, blue))
        rgb_str = f"{r},{g},{b}"
        payload = self._operate_payload(device_id, org_id, OP_ID_RGB, intensity=intensity, cool=cool, warm=warm, rgb=rgb_str)
        _LOGGER.debug("set_rgbww device_id=%s rgb=%s warm=%d cool=%d", device_id, rgb_str, warm, cool)
        return await self._post(OPERATIONS_ENDPOINT, payload)
