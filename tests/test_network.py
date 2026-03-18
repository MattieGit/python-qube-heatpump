"""Test network utilities."""

from unittest.mock import AsyncMock, mock_open, patch

import pytest

from python_qube_heatpump.network import async_get_mac_address


ARP_TABLE_CONTENT = """\
IP address       HW type     Flags       HW address            Mask     Device
192.168.5.208    0x1         0x2         00:0a:5c:94:83:15     *        eth0
192.168.5.1      0x1         0x2         d0:21:f9:5d:dd:2f     *        eth0
"""


@pytest.mark.asyncio
async def test_get_mac_address():
    """Test MAC address lookup from ARP table."""
    with (
        patch(
            "python_qube_heatpump.network.asyncio.open_connection",
            return_value=(AsyncMock(), AsyncMock()),
        ),
        patch(
            "python_qube_heatpump.network._resolve_ip",
            return_value="192.168.5.208",
        ),
        patch(
            "builtins.open",
            mock_open(read_data=ARP_TABLE_CONTENT),
        ),
    ):
        result = await async_get_mac_address("qube.local")

    assert result == "00:0a:5c:94:83:15"


@pytest.mark.asyncio
async def test_get_mac_address_not_found():
    """Test MAC address returns None when not in ARP table."""
    with (
        patch(
            "python_qube_heatpump.network.asyncio.open_connection",
            return_value=(AsyncMock(), AsyncMock()),
        ),
        patch(
            "python_qube_heatpump.network._resolve_ip",
            return_value="192.168.5.99",
        ),
        patch(
            "builtins.open",
            mock_open(read_data=ARP_TABLE_CONTENT),
        ),
    ):
        result = await async_get_mac_address("unknown.local")

    assert result is None


@pytest.mark.asyncio
async def test_get_mac_address_connection_fails():
    """Test MAC address returns None when connection fails."""
    with (
        patch(
            "python_qube_heatpump.network.asyncio.open_connection",
            side_effect=OSError,
        ),
        patch(
            "python_qube_heatpump.network._resolve_ip",
            return_value="192.168.5.208",
        ),
    ):
        result = await async_get_mac_address("qube.local")

    assert result is None


@pytest.mark.asyncio
async def test_get_mac_address_no_proc_net_arp():
    """Test MAC address returns None on non-Linux systems."""
    with (
        patch(
            "python_qube_heatpump.network.asyncio.open_connection",
            return_value=(AsyncMock(), AsyncMock()),
        ),
        patch(
            "python_qube_heatpump.network._resolve_ip",
            return_value="192.168.5.208",
        ),
        patch(
            "builtins.open",
            side_effect=FileNotFoundError,
        ),
    ):
        result = await async_get_mac_address("qube.local")

    assert result is None


@pytest.mark.asyncio
async def test_get_mac_address_with_ip_directly():
    """Test MAC address lookup when given an IP directly."""
    with (
        patch(
            "python_qube_heatpump.network.asyncio.open_connection",
            return_value=(AsyncMock(), AsyncMock()),
        ),
        patch(
            "python_qube_heatpump.network._resolve_ip",
            return_value="192.168.5.208",
        ),
        patch(
            "builtins.open",
            mock_open(read_data=ARP_TABLE_CONTENT),
        ),
    ):
        result = await async_get_mac_address("192.168.5.208")

    assert result == "00:0a:5c:94:83:15"
