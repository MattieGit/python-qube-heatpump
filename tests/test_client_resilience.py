"""Tests for QubeClient behaviour when the Modbus link fails."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ConnectionException, ModbusIOException

from python_qube_heatpump import QubeClient
from python_qube_heatpump.entities import BINARY_SENSORS, SWITCHES


def _ok_registers(address, count=1, **kwargs):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = [0] * count
    return resp


def _ok_bits(address, count=1, **kwargs):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.bits = [False] * count
    return resp


def _error_reply(*args, **kwargs):
    resp = MagicMock()
    resp.isError.return_value = True
    return resp


def _all_reads(mock_instance, side_effect):
    """Point every read function at the same side effect."""
    for name in (
        "read_coils",
        "read_discrete_inputs",
        "read_input_registers",
        "read_holding_registers",
    ):
        setattr(mock_instance, name, AsyncMock(side_effect=side_effect))


def _total_reads(mock_instance) -> int:
    return sum(
        getattr(mock_instance, name).call_count
        for name in (
            "read_coils",
            "read_discrete_inputs",
            "read_input_registers",
            "read_holding_registers",
        )
    )


def _healthy(mock_instance):
    mock_instance.read_coils = AsyncMock(side_effect=_ok_bits)
    mock_instance.read_discrete_inputs = AsyncMock(side_effect=_ok_bits)
    mock_instance.read_input_registers = AsyncMock(side_effect=_ok_registers)
    mock_instance.read_holding_registers = AsyncMock(side_effect=_ok_registers)


@pytest.fixture
def connected_client(mock_modbus_client):
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    client._connected = True
    return client, mock_instance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ConnectionException("down"),
        ModbusIOException("No response received after 3 retries"),
        TimeoutError(),
        ConnectionResetError(),
    ],
)
async def test_link_error_marks_client_disconnected(connected_client, exc):
    """A link-level failure clears is_connected and closes the transport."""
    client, mock_instance = connected_client
    _all_reads(mock_instance, exc)

    await client.read_entities_batched(SWITCHES.values())

    assert client.is_connected is False
    mock_instance.close.assert_called()


@pytest.mark.asyncio
async def test_get_all_data_stops_after_first_link_error(connected_client):
    """A dead link costs two transactions per poll, not one per entity.

    The failed block read is followed by one single-entity read that acts as
    a probe (a device may time out on a large block but answer small reads);
    when that fails too, the poll stops.
    """
    client, mock_instance = connected_client
    _all_reads(mock_instance, ModbusIOException("no response"))

    state = await client.get_all_data()

    assert state is None
    assert _total_reads(mock_instance) == 2


@pytest.mark.asyncio
async def test_batched_read_returns_every_key_after_link_error(connected_client):
    """Callers still get a value (None) for every requested entity."""
    client, mock_instance = connected_client
    _all_reads(mock_instance, ConnectionException("down"))

    results = await client.read_entities_batched(BINARY_SENSORS.values())

    assert set(results) == set(BINARY_SENSORS)
    assert all(value is None for value in results.values())


@pytest.mark.asyncio
async def test_block_timeout_with_working_single_reads_stays_connected(
    connected_client,
):
    """A block that times out while single reads work is not a dead link."""
    client, mock_instance = connected_client
    mock_instance.read_discrete_inputs = AsyncMock(
        side_effect=[ModbusIOException("no response"), _ok_bits(0), _ok_bits(1)]
    )

    entities = [BINARY_SENSORS["dout_srcpmp_val"], BINARY_SENSORS["dout_usrpmp_val"]]
    results = await client.read_entities_batched(entities)

    assert results == {e.key: False for e in entities}
    assert client.is_connected is True


@pytest.mark.asyncio
async def test_error_reply_still_falls_back_to_single_reads(connected_client):
    """A Modbus error reply is not a link failure: fall back per entity."""
    client, mock_instance = connected_client
    _all_reads(mock_instance, _error_reply)

    entities = [BINARY_SENSORS["dout_srcpmp_val"], BINARY_SENSORS["dout_usrpmp_val"]]
    await client.read_entities_batched(entities)

    # one block read plus one single read per entity
    assert mock_instance.read_discrete_inputs.call_count == 3
    assert client.is_connected is True


@pytest.mark.asyncio
async def test_single_read_fallback_stops_at_link_error(connected_client):
    """If the link dies during the per-entity fallback, the rest is skipped."""
    client, mock_instance = connected_client
    mock_instance.read_discrete_inputs = AsyncMock(
        side_effect=[_error_reply(), ConnectionException("down")] + [_ok_bits(0)] * 10
    )

    entities = [
        BINARY_SENSORS["dout_srcpmp_val"],
        BINARY_SENSORS["dout_usrpmp_val"],
        BINARY_SENSORS["dout_fourwayvlv_val"],
    ]
    results = await client.read_entities_batched(entities)

    assert mock_instance.read_discrete_inputs.call_count == 2
    assert results == {e.key: None for e in entities}
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_get_all_data_reconnects_on_next_poll(connected_client):
    """After a lost link the next poll reconnects and returns data again."""
    client, mock_instance = connected_client
    _all_reads(mock_instance, ConnectionException("down"))
    assert await client.get_all_data() is None
    assert client.is_connected is False

    mock_instance.connect = AsyncMock(return_value=True)
    _healthy(mock_instance)
    state = await client.get_all_data()

    assert state is not None
    mock_instance.connect.assert_awaited_once()
    assert client.is_connected is True


@pytest.mark.asyncio
async def test_read_entity_link_error_marks_disconnected(connected_client):
    """Single-entity reads detect a lost link too."""
    client, mock_instance = connected_client
    _all_reads(mock_instance, ConnectionException("down"))

    assert await client.read_entity(BINARY_SENSORS["dout_srcpmp_val"]) is None
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_write_link_error_marks_disconnected(connected_client):
    """Writes that hit a lost link return False and clear is_connected."""
    client, mock_instance = connected_client
    mock_instance.write_coil = AsyncMock(side_effect=ConnectionException("down"))

    assert await client.write_switch("bms_summerwinter", True) is False
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_failure_warns_again_after_recovery(connected_client, caplog):
    """Warn-once resets when the target reads fine again."""
    client, mock_instance = connected_client
    entity = BINARY_SENSORS["dout_srcpmp_val"]
    mock_instance.read_discrete_inputs = AsyncMock(
        side_effect=[
            _error_reply(),
            _error_reply(),
            _ok_bits(0),
            _error_reply(),
            _error_reply(),
        ]
    )
    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        await client.read_entities_batched([entity])  # block fails, single fails
        await client.read_entities_batched([entity])  # recovers
        await client.read_entities_batched([entity])  # block fails again

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "block" in r.getMessage()
    ]
    assert len(warnings) == 2


@pytest.mark.asyncio
async def test_link_failure_warns_again_after_recovery(connected_client, caplog):
    """A second outage days later is logged at WARNING again."""
    client, mock_instance = connected_client
    entity = BINARY_SENSORS["dout_srcpmp_val"]
    mock_instance.read_discrete_inputs = AsyncMock(
        side_effect=[OSError("down"), _ok_bits(0), OSError("down again")]
    )

    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        await client.read_entity(entity)
        await client.read_entity(entity)
        await client.read_entity(entity)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
