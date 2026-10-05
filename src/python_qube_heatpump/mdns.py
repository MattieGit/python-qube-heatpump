"""Device information from the Qube's mDNS advertisement.

The Qube's Carel controller advertises a ``_workstation._tcp`` service whose
TXT record carries the panel software version (``ProjectRelease``), the
controller firmware (``FWRelease``) and a stable ``Uuid``. The software
version register (77) returns 0.0 on recent firmware, so this is the only
reliable source of the version shown on the panel.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
import logging
import socket

from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

_LOGGER = logging.getLogger(__name__)

SERVICE_TYPE = "_workstation._tcp.local."
CAREL_VENDOR_ID = "000A5C"

# Per-service resolve timeout (ms) and overall lookup timeout (s)
_RESOLVE_TIMEOUT_MS = 1500
DEFAULT_LOOKUP_TIMEOUT = 5.0


@dataclass(frozen=True)
class QubeDeviceInfo:
    """Device information advertised by the Qube over mDNS."""

    uuid: str
    software_version: str | None
    controller_firmware: str | None
    project_name: str | None


def _decode(value: str | bytes | None) -> str | None:
    """Decode a TXT value; empty values become None."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value or None


def parse_device_info(
    properties: Mapping[str, str | None] | Mapping[bytes, bytes | None],
) -> QubeDeviceInfo | None:
    """Parse the TXT properties of a Qube ``_workstation._tcp`` service.

    Accepts both raw zeroconf properties (bytes) and decoded properties
    (str, as Home Assistant passes them). Keys are matched case-insensitively.

    Returns None when the record does not come from a Carel controller or
    has no Uuid.
    """
    txt: dict[str, str | None] = {}
    for key, value in properties.items():
        name = _decode(key)
        if name is not None:
            txt[name.lower()] = _decode(value)

    vendor = txt.get("vendor")
    uuid = txt.get("uuid")
    if vendor is None or vendor.upper() != CAREL_VENDOR_ID or uuid is None:
        return None

    return QubeDeviceInfo(
        uuid=uuid,
        software_version=txt.get("projectrelease"),
        controller_firmware=txt.get("fwrelease"),
        project_name=txt.get("projectname"),
    )


def _resolve_ip(host: str) -> str | None:
    """Resolve a hostname to an IPv4 address."""
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def _matches_host(info: AsyncServiceInfo, host: str, ip: str | None) -> bool:
    """Return True if the resolved service belongs to the given host."""
    if ip is not None and ip in info.parsed_addresses():
        return True
    server = (info.server or "").lower().rstrip(".")
    return server == host.lower().rstrip(".")


async def async_get_device_info(
    host: str,
    aiozc: AsyncZeroconf,
    timeout: float = DEFAULT_LOOKUP_TIMEOUT,
) -> QubeDeviceInfo | None:
    """Look up the mDNS device information of the Qube at ``host``.

    Browses ``_workstation._tcp`` services and returns the first Carel
    record whose address (or mDNS hostname) matches ``host``. The caller
    owns ``aiozc``; Home Assistant integrations must pass the shared
    instance from ``zeroconf.async_get_async_instance``.

    Returns None if no matching record is found within ``timeout`` seconds,
    for example when mDNS is not forwarded between VLANs.
    """
    ip = await asyncio.to_thread(_resolve_ip, host)
    names: asyncio.Queue[str] = asyncio.Queue()
    seen: set[str] = set()

    def _on_change(
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change is not ServiceStateChange.Removed and name not in seen:
            seen.add(name)
            names.put_nowait(name)

    browser = AsyncServiceBrowser(aiozc.zeroconf, [SERVICE_TYPE], handlers=[_on_change])
    try:
        async with asyncio.timeout(timeout):
            while True:
                name = await names.get()
                info = AsyncServiceInfo(SERVICE_TYPE, name)
                if not await info.async_request(aiozc.zeroconf, _RESOLVE_TIMEOUT_MS):
                    continue
                if not _matches_host(info, host, ip):
                    continue
                if (device := parse_device_info(info.properties)) is not None:
                    return device
    except TimeoutError:
        _LOGGER.debug("No mDNS device information found for %s", host)
        return None
    finally:
        with contextlib.suppress(Exception):
            await browser.async_cancel()
