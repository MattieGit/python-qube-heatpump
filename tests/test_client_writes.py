"""Tests for write validation and SG Ready writes in QubeClient."""

import logging
import math
from unittest.mock import AsyncMock

import pytest
from helpers import float_from_regs
from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import ReadEvent, WriteEvent

from python_qube_heatpump.entities import SENSORS
from python_qube_heatpump.entities.base import (
    DataType,
    EntityDef,
    InputType,
    Platform,
)


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
async def test_write_setpoint_accepts_values_in_range(client, unit, writes, value):
    assert await client.write_setpoint("setpoint_dhw", value) is True
    assert [(w.register_type, w.address, w.function_code) for w in writes] == [
        ("holding", 173, 0x10)
    ]
    assert float_from_regs([unit.holding[173], unit.holding[174]]) == pytest.approx(
        value
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [39.9, 65.1, 500.0, -10.0])
async def test_write_setpoint_rejects_out_of_range(client, writes, value):
    assert await client.write_setpoint("setpoint_dhw", value) is False
    assert writes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
async def test_write_setpoint_rejects_non_finite(client, writes, value):
    assert await client.write_setpoint("usr_pid_heatsetp", value) is False
    assert writes == []


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
    client, writes, monkeypatch, data_type, value, written
):
    monkeypatch.setitem(SENSORS, "test_int_setpoint", _int_entity(data_type))
    assert await client.write_setpoint("test_int_setpoint", value) is True
    assert writes == [WriteEvent("holding", 500, [written], 0x06)]


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
    client, writes, monkeypatch, data_type, value
):
    monkeypatch.setitem(SENSORS, "test_int_setpoint", _int_entity(data_type))
    assert await client.write_setpoint("test_int_setpoint", value) is False
    assert writes == []


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
async def test_set_sg_ready_mode_writes_both_coils_at_once(
    client, unit, writes, mode, bits
):
    assert await client.set_sg_ready_mode(mode) is True
    assert writes == [WriteEvent("coil", 65, bits, 0x0F)]
    assert [unit.coil[65], unit.coil[66]] == bits


@pytest.mark.asyncio
async def test_set_sg_ready_mode_falls_back_when_multi_write_unsupported(
    client, unit, writes
):
    """A device that rejects FC15 still gets the mode via two single writes."""
    unit.write_coils = AsyncMock(side_effect=IllegalFunctionError())

    assert await client.set_sg_ready_mode("plus") is True
    unit.write_coils.assert_awaited_once_with(65, [False, True])
    assert writes == [
        WriteEvent("coil", 65, [False], 0x05),
        WriteEvent("coil", 66, [True], 0x05),
    ]


@pytest.mark.asyncio
async def test_set_sg_ready_mode_link_error_does_not_fall_back(
    client, unit, writes, mock_modbus_connection, mocker
):
    await mock_modbus_connection.connect()
    unit.fail_write(65, ModbusConnectionError("down"), register_type="coil")
    write_coil = mocker.spy(unit, "write_coil")

    assert await client.set_sg_ready_mode("max") is False
    write_coil.assert_not_called()
    assert writes == []
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_get_sg_ready_mode_reads_both_coils_in_one_request(client, unit):
    unit.coil[65] = [True, False]

    assert await client.get_sg_ready_mode() == "block"
    assert unit.read_events == [ReadEvent("coil", 65, 2)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("write", "register_type", "address", "method"),
    [
        (
            lambda c: c.write_setpoint("setpoint_dhw", 50.0),
            "holding",
            173,
            "write_registers",
        ),
        (lambda c: c.write_switch("bms_summerwinter", True), "coil", 22, "write_coil"),
        (lambda c: c.set_sg_ready_mode("max"), "coil", 65, "write_coils"),
    ],
    ids=["setpoint", "switch", "sg_ready"],
)
async def test_writes_are_never_retried(
    client,
    unit,
    mock_modbus_connection,
    mocker,
    caplog,
    write,
    register_type,
    address,
    method,
):
    """A write that times out is logged as an error, not sent again."""
    await mock_modbus_connection.connect()
    unit.fail_write(
        address, ModbusTimeoutError("no response"), register_type=register_type
    )
    attempts = mocker.spy(unit, method)

    with caplog.at_level(logging.WARNING, logger="python_qube_heatpump.client"):
        assert await write(client) is False

    assert attempts.await_count == 1
    assert [r.levelname for r in caplog.records] == ["ERROR"]
    assert "no response" in caplog.records[0].getMessage()
    assert client.is_connected is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("write", "register_type", "address", "message"),
    [
        (
            lambda c: c.write_setpoint("setpoint_dhw", 50.0),
            "holding",
            173,
            "Error writing setpoint setpoint_dhw",
        ),
        (
            lambda c: c.write_switch("bms_summerwinter", True),
            "coil",
            22,
            "Error writing switch bms_summerwinter",
        ),
    ],
    ids=["setpoint", "switch"],
)
async def test_write_error_reply_warns_and_keeps_link(
    client, unit, mock_modbus_connection, caplog, write, register_type, address, message
):
    """An error reply to a write returns False with a WARNING; the link stays up."""
    await mock_modbus_connection.connect()
    unit.fail_write(address, IllegalDataAddressError(), register_type=register_type)

    with caplog.at_level(logging.WARNING, logger="python_qube_heatpump.client"):
        assert await write(client) is False

    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        ("WARNING", message)
    ]
    assert client.is_connected is True
