"""Tests for QubeClient behaviour when the Modbus link fails."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from helpers import script_reads
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusProtocolError,
    ModbusTimeoutError,
)
from modbus_connection.mock import ReadEvent

from python_qube_heatpump import QubeClient
from python_qube_heatpump.entities import BINARY_SENSORS, SENSORS, SWITCHES

_TWO_DISCRETE = [BINARY_SENSORS["dout_srcpmp_val"], BINARY_SENSORS["dout_usrpmp_val"]]


@pytest_asyncio.fixture
async def connected(client, mock_modbus_connection):
    """The shared client with its link up."""
    await mock_modbus_connection.connect()
    assert client.is_connected is True
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ModbusConnectionError("down"),
        ModbusTimeoutError("no response"),
        TimeoutError(),
        ConnectionResetError(),
    ],
)
async def test_link_error_marks_client_disconnected(connected, unit, exc):
    """A link-level failure drops the link, so is_connected turns False."""
    unit.fail_requests(exc)

    await connected.read_entities_batched(SWITCHES.values())

    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_get_all_data_stops_after_first_link_error(connected, unit):
    """A connection error costs one transaction per poll, not one per entity."""
    unit.fail_requests(ModbusConnectionError("down"))

    state = await connected.get_all_data()

    assert state is None
    assert len(unit.read_events) == 1
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_batched_read_returns_every_key_after_link_error(connected, unit):
    """Callers still get a value (None) for every requested entity."""
    unit.fail_requests(ModbusConnectionError("down"))

    results = await connected.read_entities_batched(BINARY_SENSORS.values())

    assert set(results) == set(BINARY_SENSORS)
    assert all(value is None for value in results.values())


@pytest.mark.asyncio
async def test_error_reply_still_falls_back_to_single_reads(connected, unit):
    """A Modbus error reply is not a link failure: fall back per entity."""
    unit.fail_requests(IllegalDataAddressError())

    results = await connected.read_entities_batched(_TWO_DISCRETE)

    # one block read plus one single read per entity
    assert unit.read_events == [
        ReadEvent("discrete", 0, 2),
        ReadEvent("discrete", 0, 1),
        ReadEvent("discrete", 1, 1),
    ]
    assert results == {e.key: None for e in _TWO_DISCRETE}
    assert connected.is_connected is True


@pytest.mark.asyncio
async def test_single_read_fallback_stops_at_link_error(connected, unit):
    """If the link dies during the per-entity fallback, the rest is skipped."""
    script_reads(
        unit,
        "read_discrete_inputs",
        IllegalDataAddressError(),
        ModbusConnectionError("down"),
    )

    entities = [*_TWO_DISCRETE, BINARY_SENSORS["dout_fourwayvlv_val"]]
    results = await connected.read_entities_batched(entities)

    assert len(unit.read_events) == 2
    assert results == {e.key: None for e in entities}
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_get_all_data_reconnects_on_next_poll(
    owned_client, owned_unit, owned_connection, mocker
):
    """After a lost link the next poll reconnects and returns data again."""
    connects = mocker.spy(owned_connection, "_connect_client")
    owned_unit.fail_requests(ModbusConnectionError("down"))
    assert await owned_client.get_all_data() is None
    assert owned_client.is_connected is False
    assert connects.call_count == 1

    owned_unit.fail_requests(None)
    state = await owned_client.get_all_data()

    assert state is not None
    assert connects.call_count == 2
    assert owned_client.is_connected is True


@pytest.mark.asyncio
async def test_read_entity_link_error_marks_disconnected(connected, unit):
    """Single-entity reads detect a lost link too."""
    unit.fail_requests(ModbusConnectionError("down"))

    assert await connected.read_entity(BINARY_SENSORS["dout_srcpmp_val"]) is None
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_write_link_error_marks_disconnected(connected, unit):
    """Writes that hit a lost link return False and clear is_connected."""
    unit.fail_write(22, ModbusConnectionError("down"), register_type="coil")

    assert await connected.write_switch("bms_summerwinter", True) is False
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_failure_warns_again_after_recovery(connected, unit, caplog):
    """Warn-once resets when the target reads fine again."""
    entity = BINARY_SENSORS["dout_srcpmp_val"]
    script_reads(
        unit,
        "read_discrete_inputs",
        IllegalDataAddressError(),
        IllegalDataAddressError(),
        None,
        IllegalDataAddressError(),
        IllegalDataAddressError(),
    )
    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        await connected.read_entities_batched([entity])  # block fails, single fails
        await connected.read_entities_batched([entity])  # recovers
        await connected.read_entities_batched([entity])  # block fails again

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "block" in r.getMessage()
    ]
    assert len(warnings) == 2


@pytest.mark.asyncio
async def test_link_failure_warns_again_after_recovery(connected, unit, caplog):
    """A second outage days later is logged at WARNING again."""
    entity = BINARY_SENSORS["dout_srcpmp_val"]
    script_reads(
        unit, "read_discrete_inputs", OSError("down"), None, OSError("down again")
    )

    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        await connected.read_entity(entity)
        await connected.read_entity(entity)
        await connected.read_entity(entity)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2


# --- Block-read retries ---------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc", [ModbusTimeoutError("no response"), ModbusProtocolError("garbled")]
)
async def test_missed_block_response_is_retried(connected, unit, caplog, exc):
    """One missed or garbled response costs one extra read, not the poll."""
    assert await connected.get_all_data() is not None
    healthy = list(unit.read_events)
    unit.read_events.clear()
    unit.discrete[0] = True  # dout_srcpmp_val
    script_reads(unit, "read_discrete_inputs", exc)

    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        state = await connected.get_all_data()

    assert state is not None
    assert state.dout_srcpmp_val is True
    assert len(unit.read_events) == len(healthy) + 1
    retried = [e for e in unit.read_events if e.register_type == "discrete"]
    assert len(retried) == 2
    assert retried[0] == retried[1]
    assert connected.is_connected is True
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.asyncio
async def test_two_timeouts_abort_the_poll(connected, unit):
    """A block that times out twice means the device is unreachable."""
    unit.fail_requests(ModbusTimeoutError("no response"))

    assert await connected.get_all_data() is None
    assert len(unit.read_events) == 2
    assert unit.read_events[0] == unit.read_events[1]
    assert connected.is_connected is False

    unit.read_events.clear()
    results = await connected.get_all_entities()

    assert len(unit.read_events) == 2
    assert set(results) == set(SENSORS) | set(BINARY_SENSORS) | set(SWITCHES)
    assert all(value is None for value in results.values())
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_connection_error_is_not_retried(connected, unit):
    """A refused or dropped connection is not worth a second block read."""
    unit.fail_requests(ModbusConnectionError("down"))

    results = await connected.read_entities_batched(_TWO_DISCRETE)

    assert unit.read_events == [ReadEvent("discrete", 0, 2)]
    assert results == {e.key: None for e in _TWO_DISCRETE}
    assert connected.is_connected is False


@pytest.mark.asyncio
async def test_error_reply_is_not_retried(connected, unit):
    """An error reply to a block falls back to single reads without a retry."""
    unit.discrete[0] = [True, False]
    script_reads(unit, "read_discrete_inputs", IllegalDataAddressError())

    results = await connected.read_entities_batched(_TWO_DISCRETE)

    assert unit.read_events == [
        ReadEvent("discrete", 0, 2),
        ReadEvent("discrete", 0, 1),
        ReadEvent("discrete", 1, 1),
    ]
    assert results == {"dout_srcpmp_val": True, "dout_usrpmp_val": False}
    assert connected.is_connected is True


@pytest.mark.asyncio
async def test_repeated_protocol_error_falls_back_to_single_reads(connected, unit):
    """A block garbled on both attempts is not a dead link: read per entity."""
    unit.discrete[0] = [True, False]
    script_reads(
        unit,
        "read_discrete_inputs",
        ModbusProtocolError("garbled"),
        ModbusProtocolError("garbled"),
    )

    results = await connected.read_entities_batched(_TWO_DISCRETE)

    assert unit.read_events == [
        ReadEvent("discrete", 0, 2),
        ReadEvent("discrete", 0, 2),
        ReadEvent("discrete", 0, 1),
        ReadEvent("discrete", 1, 1),
    ]
    assert results == {"dout_srcpmp_val": True, "dout_usrpmp_val": False}
    assert connected.is_connected is True


# --- Connection ownership -------------------------------------------------


@pytest.mark.asyncio
async def test_shared_unit_connect_and_close_leave_the_link_alone(
    client, unit, mock_modbus_connection
):
    """With a caller-owned unit, connect() and close() do not touch the link."""
    assert await client.connect() is True
    assert unit.connected is False  # the unit connects on its first request

    await mock_modbus_connection.connect()
    await client.close()
    assert unit.connected is True

    assert await client.read_binary_sensor("dout_srcpmp_val") is False


@pytest.mark.asyncio
async def test_shared_unit_get_all_data_has_no_backoff(client, unit):
    """Backoff only applies to a connection the client owns."""
    unit.fail_requests(ModbusConnectionError("down"))
    assert await client.get_all_data() is None

    unit.fail_requests(None)
    assert await client.get_all_data() is not None
    assert client._backoff_seconds == 0.0


@pytest.mark.asyncio
async def test_owned_connect_failure_returns_false(
    owned_client, owned_connection, monkeypatch
):
    """connect() reports an unreachable device as False instead of raising."""
    monkeypatch.setattr(
        owned_connection,
        "connect",
        AsyncMock(side_effect=ModbusConnectionError("refused")),
    )

    assert await owned_client.connect() is False
    assert owned_client.is_connected is False
    assert await owned_client.get_all_data() is None
    assert owned_client._backoff_seconds == 1.0


@pytest.mark.asyncio
async def test_owned_connect_timeout_returns_false(
    owned_client, owned_connection, monkeypatch
):
    """connect() gives up after TIMEOUT seconds."""
    hang = asyncio.Event()

    async def connect_forever() -> None:
        await hang.wait()

    monkeypatch.setattr(owned_connection, "connect", connect_forever)
    monkeypatch.setattr(QubeClient, "TIMEOUT", 0.01)

    assert await owned_client.connect() is False
    assert owned_client.is_connected is False
    hang.set()  # let the abandoned attempt finish
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_owned_close_disconnects_and_client_still_works(owned_client, owned_unit):
    """close() drops the owned link; the next request connects again."""
    assert await owned_client.connect() is True
    owned_client._backoff_seconds = 8.0

    await owned_client.close()

    assert owned_unit.connected is False
    assert owned_client._backoff_seconds == 0.0
    assert await owned_client.get_all_data() is not None
    assert owned_client.is_connected is True
