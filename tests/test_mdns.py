"""Test mDNS device information lookup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zeroconf import ServiceStateChange

from python_qube_heatpump.mdns import (
    SERVICE_TYPE,
    QubeDeviceInfo,
    async_get_device_info,
    parse_device_info,
)

# TXT record captured from a Qube (fw 4.1.00)
QUBE_TXT = {
    b"Vendor": b"000A5C",
    b"MachineType": b"312",
    b"HWCode": b"344",
    b"InterfaceType": b"11",
    b"Uuid": b"000100000007B5EA",
    b"FWRelease": b"v5.1.007",
    b"ToolRelease": b"5.1.9",
    b"ProjectRelease": b"4.1.00",
    b"ProjectName": b"DEQSIHPB000CR",
    b"OemId": b"",
    b"MachineCode": None,
}

QUBE_INFO = QubeDeviceInfo(
    uuid="000100000007B5EA",
    software_version="4.1.00",
    controller_firmware="v5.1.007",
    project_name="DEQSIHPB000CR",
)


def test_parse_bytes_properties():
    """Raw zeroconf properties are parsed."""
    assert parse_device_info(QUBE_TXT) == QUBE_INFO


def test_parse_str_properties_case_insensitive():
    """Decoded properties with different key case are parsed."""
    props = {
        "vendor": "000a5c",
        "UUID": "000100000007B5EA",
        "projectrelease": "4.1.00",
    }
    assert parse_device_info(props) == QubeDeviceInfo(
        uuid="000100000007B5EA",
        software_version="4.1.00",
        controller_firmware=None,
        project_name=None,
    )


@pytest.mark.parametrize(
    "props",
    [
        {b"Vendor": b"001122", b"Uuid": b"X"},
        {b"Vendor": b"000A5C"},
        {b"Vendor": b"000A5C", b"Uuid": b""},
        {b"Uuid": b"X"},
        {},
    ],
)
def test_parse_rejects_non_qube(props):
    """Records from other vendors or without a Uuid are ignored."""
    assert parse_device_info(props) is None


def _service(name: str, addresses: list[str], server: str, props: dict):
    """Build a fake resolved AsyncServiceInfo."""
    info = MagicMock()
    info.name = name
    info.server = server
    info.properties = props
    info.parsed_addresses.return_value = addresses
    info.async_request = AsyncMock(return_value=True)
    return info


def _patch_zeroconf(services: dict):
    """Patch the browser to announce ``services`` and the resolver to return them."""

    def browser(zc, types, handlers):
        assert types == [SERVICE_TYPE]
        for name in services:
            handlers[0](
                zeroconf=zc,
                service_type=SERVICE_TYPE,
                name=name,
                state_change=ServiceStateChange.Added,
            )
        mock = MagicMock()
        mock.async_cancel = AsyncMock()
        return mock

    return (
        patch("python_qube_heatpump.mdns.AsyncServiceBrowser", side_effect=browser),
        patch(
            "python_qube_heatpump.mdns.AsyncServiceInfo",
            side_effect=lambda type_, name: services[name],
        ),
    )


@pytest.mark.asyncio
async def test_lookup_matches_ip():
    """The Carel record whose address matches the host is returned."""
    services = {
        "PC._workstation._tcp.local.": _service(
            "PC", ["192.168.1.10"], "pc.local.", {b"Vendor": b"000A5C", b"Uuid": b"Y"}
        ),
        "Qube._workstation._tcp.local.": _service(
            "Qube", ["192.168.5.208"], "Qube.local.", QUBE_TXT
        ),
    }
    browser, info = _patch_zeroconf(services)
    with (
        browser,
        info,
        patch("python_qube_heatpump.mdns._resolve_ip", return_value="192.168.5.208"),
    ):
        result = await async_get_device_info("192.168.5.208", MagicMock())

    assert result == QUBE_INFO


@pytest.mark.asyncio
async def test_lookup_matches_mdns_hostname():
    """A .local host that does not resolve via DNS matches on the SRV server."""
    services = {
        "Qube._workstation._tcp.local.": _service(
            "Qube", ["192.168.5.208"], "Qube.local.", QUBE_TXT
        ),
    }
    browser, info = _patch_zeroconf(services)
    with (
        browser,
        info,
        patch("python_qube_heatpump.mdns._resolve_ip", return_value=None),
    ):
        result = await async_get_device_info("qube.local", MagicMock())

    assert result == QUBE_INFO


@pytest.mark.asyncio
async def test_lookup_skips_unresolved_and_non_qube():
    """Services that fail to resolve or are not Carel are skipped until timeout."""
    unresolved = _service("A", ["192.168.5.208"], "a.local.", QUBE_TXT)
    unresolved.async_request = AsyncMock(return_value=False)
    services = {
        "A._workstation._tcp.local.": unresolved,
        "B._workstation._tcp.local.": _service(
            "B", ["192.168.5.208"], "b.local.", {b"Vendor": b"001122"}
        ),
    }
    browser, info = _patch_zeroconf(services)
    with (
        browser,
        info,
        patch("python_qube_heatpump.mdns._resolve_ip", return_value="192.168.5.208"),
    ):
        result = await async_get_device_info("192.168.5.208", MagicMock(), timeout=0.05)

    assert result is None


@pytest.mark.asyncio
async def test_lookup_times_out_without_services():
    """No advertisement (e.g. mDNS blocked) returns None after the timeout."""
    browser, info = _patch_zeroconf({})
    with (
        browser,
        info,
        patch("python_qube_heatpump.mdns._resolve_ip", return_value="10.0.0.5"),
    ):
        result = await async_get_device_info("10.0.0.5", MagicMock(), timeout=0.05)

    assert result is None
