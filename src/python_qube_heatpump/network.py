"""Network utilities for Qube Heat Pump."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket

_LOGGER = logging.getLogger(__name__)

MODBUS_PORT = 502


def _resolve_ip(host: str) -> str | None:
    """Resolve hostname to IP address."""
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def _read_arp_table(ip: str) -> str | None:
    """Read MAC address from /proc/net/arp for the given IP.

    Only works on Linux. Returns None on other platforms.
    """
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    mac = parts[3]
                    if mac != "00:00:00:00:00:00":
                        return mac.lower()
    except FileNotFoundError:
        _LOGGER.debug("/proc/net/arp not found — not running on Linux")
    return None


async def async_get_mac_address(host: str, port: int = MODBUS_PORT) -> str | None:
    """Get the MAC address of a device by connecting and reading ARP.

    Opens a brief TCP connection to populate the ARP table, then reads
    the MAC address from /proc/net/arp.

    Only works on Linux (where /proc/net/arp exists). Returns None on
    other platforms or if the device is not on the same L2 network.

    Args:
        host: Hostname or IP address of the device.
        port: TCP port to connect to (default: 502 for Modbus).

    Returns:
        MAC address as lowercase colon-separated string, or None.
    """
    ip = _resolve_ip(host)
    if ip is None:
        _LOGGER.debug("Could not resolve host %s to IP", host)
        return None

    # Open a brief TCP connection to populate ARP table
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=5
        )
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
    except (OSError, TimeoutError):
        _LOGGER.debug("Could not connect to %s:%s to populate ARP", ip, port)
        return None

    return _read_arp_table(ip)
