"""Tests for write validation and SG Ready writes in QubeClient."""

import math
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ConnectionException

from python_qube_heatpump import QubeClient
from python_qube_heatpump.entities import SENSORS
from python_qube_heatpump.entities.base import (
    DataType,
    EntityDef,
    InputType,
    Platform,
)


def _ok():
    resp = MagicMock()
    resp.isError.return_value = False
    return resp


def _error_reply():
    resp = MagicMock()
    resp.isError.return_value = True
    return resp


def _float_from_regs(regs):
    return struct.unpack(">f", struct.pack(">I", (regs[0] << 16) | regs[1]))[0]


@pytest.fixture
def client(mock_modbus_client):
    qube = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.write_registers = AsyncMock(return_value=_ok())
    mock_instance.write_register = AsyncMock(return_value=_ok())
    mock_instance.write_coil = AsyncMock(return_value=_ok())
    mock_instance.write_coils = AsyncMock(return_value=_ok())
    qube._client = mock_instance
    qube._connected = True
    return qube, mock_instance


# Ranges the HA core and HACS integrations expose for these setpoints
@pytest.mark.parametrize(
    ("key", "low", "high"),
    [
        ("setpoint_dhw", 40.0, 65.0),
        ("tapw_timeprogram_dhwsetp_nolinq", 40.0, 65.0),
        ("usr_pid_heatsetp", 20.0, 65.0),
        ("usr_pid_coolsetp", 7.0, 25.0),
    ],
)
def test_writable_setpoints_have_safe_ranges(key, low, high):
    entity = SENSORS[key]
    assert entity.min_value == low
    assert entity.max_value == high


def test_every_writable_sensor_has_a_range():
    for entity in SENSORS.values():
        if entity.writable:
            assert entity.min_value is not None, entity.key
            assert entity.max_value is not None, entity.key


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [40.0, 52.5, 65.0])
async def test_write_setpoint_accepts_values_in_range(client, value):
    qube, mock_instance = client
    assert await qube.write_setpoint("setpoint_dhw", value) is True
    regs = mock_instance.write_registers.call_args.args[1]
    assert _float_from_regs(regs) == pytest.approx(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [39.9, 65.1, 500.0, -10.0])
async def test_write_setpoint_rejects_out_of_range(client, value):
    qube, mock_instance = client
    assert await qube.write_setpoint("setpoint_dhw", value) is False
    mock_instance.write_registers.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
async def test_write_setpoint_rejects_non_finite(client, value):
    qube, mock_instance = client
    assert await qube.write_setpoint("usr_pid_heatsetp", value) is False
    mock_instance.write_registers.assert_not_called()


def _int_entity(data_type, **kwargs):
    return EntityDef(
        key="test_int_setpoint",
        name="Test",
        address=500,
        input_type=InputType.HOLDING_REGISTER,
        data_type=data_type,
        platform=Platform.SENSOR,
        writable=True,
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data_type", "value", "written"),
    [
        (DataType.UINT16, 21.6, 22),
        (DataType.UINT16, 21.4, 21),
        (DataType.INT16, -2.6, 65536 - 3),
    ],
)
async def test_write_setpoint_rounds_16bit_values(
    client, monkeypatch, data_type, value, written
):
    qube, mock_instance = client
    monkeypatch.setitem(SENSORS, "test_int_setpoint", _int_entity(data_type))
    assert await qube.write_setpoint("test_int_setpoint", value) is True
    assert mock_instance.write_register.call_args.args[1] == written


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data_type", "value"),
    [
        (DataType.UINT16, -1),
        (DataType.UINT16, 65536),
        (DataType.INT16, 32768),
        (DataType.INT16, -32769),
    ],
)
async def test_write_setpoint_rejects_16bit_overflow(
    client, monkeypatch, data_type, value
):
    qube, mock_instance = client
    monkeypatch.setitem(SENSORS, "test_int_setpoint", _int_entity(data_type))
    assert await qube.write_setpoint("test_int_setpoint", value) is False
    mock_instance.write_register.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "bits"),
    [
        ("off", [False, False]),
        ("block", [True, False]),
        ("plus", [False, True]),
        ("max", [True, True]),
    ],
)
async def test_set_sg_ready_mode_writes_both_coils_at_once(client, mode, bits):
    qube, mock_instance = client
    assert await qube.set_sg_ready_mode(mode) is True
    mock_instance.write_coils.assert_awaited_once()
    call = mock_instance.write_coils.call_args
    assert call.args == (65, bits)
    mock_instance.write_coil.assert_not_called()


@pytest.mark.asyncio
async def test_set_sg_ready_mode_falls_back_when_multi_write_unsupported(client):
    """A device that rejects FC15 still gets the mode via two single writes."""
    qube, mock_instance = client
    mock_instance.write_coils = AsyncMock(return_value=_error_reply())

    assert await qube.set_sg_ready_mode("plus") is True
    calls = mock_instance.write_coil.call_args_list
    assert [c.args for c in calls] == [(65, False), (66, True)]


@pytest.mark.asyncio
async def test_set_sg_ready_mode_link_error_does_not_fall_back(client):
    qube, mock_instance = client
    mock_instance.write_coils = AsyncMock(side_effect=ConnectionException("down"))

    assert await qube.set_sg_ready_mode("max") is False
    mock_instance.write_coil.assert_not_called()
    assert qube.is_connected is False


@pytest.mark.asyncio
async def test_get_sg_ready_mode_reads_both_coils_in_one_request(client):
    qube, mock_instance = client
    resp = _ok()
    resp.bits = [True, False, False, False, False, False, False, False]
    mock_instance.read_coils = AsyncMock(return_value=resp)

    assert await qube.get_sg_ready_mode() == "block"
    mock_instance.read_coils.assert_awaited_once()
    assert mock_instance.read_coils.call_args.args[0] == 65
    assert mock_instance.read_coils.call_args.kwargs["count"] == 2
