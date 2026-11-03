"""Tests for batched block reads in QubeClient."""

import pytest
from helpers import float32_regs, script_reads
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import ReadEvent

from python_qube_heatpump.entities import BINARY_SENSORS, SENSORS, SWITCHES
from python_qube_heatpump.entities.base import (
    DataType,
    EntityDef,
    InputType,
    Platform,
)


@pytest.mark.asyncio
async def test_batched_discrete_inputs_single_transaction(client, unit):
    """Adjacent discrete inputs are read in one block transaction."""
    unit.discrete[0] = [True, False, True]

    entities = [
        BINARY_SENSORS["dout_srcpmp_val"],  # address 0
        BINARY_SENSORS["dout_usrpmp_val"],  # address 1
        BINARY_SENSORS["dout_fourwayvlv_val"],  # address 2
    ]
    results = await client.read_entities_batched(entities)

    assert len(unit.read_events) == 1
    event = unit.read_events[0]
    assert (event.register_type, event.address) == ("discrete", 0)
    assert event.count >= 3
    assert results == {
        "dout_srcpmp_val": True,
        "dout_usrpmp_val": False,
        "dout_fourwayvlv_val": True,
    }


@pytest.mark.asyncio
async def test_batched_input_registers_decode_float32(client, unit):
    """Adjacent float32 input registers decode correctly from one block."""
    unit.input[20] = float32_regs(24.5) + float32_regs(25.0)

    entities = [
        SENSORS["temp_supply"],  # address 20, float32
        SENSORS["temp_return"],  # address 22, float32
    ]
    results = await client.read_entities_batched(entities)

    assert unit.read_events == [ReadEvent("input", 20, 4)]
    assert round(results["temp_supply"], 1) == 24.5
    assert round(results["temp_return"], 1) == 25.0


@pytest.mark.asyncio
async def test_batched_far_apart_registers_split_into_blocks(client, unit):
    """Registers far apart are read in separate block transactions."""
    unit.holding[0] = float32_regs(1.0)
    unit.holding[500] = float32_regs(2.0)

    ent_a = EntityDef(
        key="a",
        name="A",
        address=0,
        input_type=InputType.HOLDING_REGISTER,
        platform=Platform.SENSOR,
        data_type=DataType.FLOAT32,
    )
    ent_b = EntityDef(
        key="b",
        name="B",
        address=500,
        input_type=InputType.HOLDING_REGISTER,
        platform=Platform.SENSOR,
        data_type=DataType.FLOAT32,
    )
    results = await client.read_entities_batched([ent_a, ent_b])

    assert unit.read_events == [
        ReadEvent("holding", 0, 2),
        ReadEvent("holding", 500, 2),
    ]
    assert results == {"a": 1.0, "b": 2.0}


@pytest.mark.asyncio
async def test_batched_block_failure_falls_back_to_individual_reads(client, unit):
    """If a block read gets an error reply, its entities are read individually."""
    unit.input[20] = float32_regs(24.5) + float32_regs(25.0)
    script_reads(unit, "read_input_registers", IllegalDataAddressError())

    entities = [SENSORS["temp_supply"], SENSORS["temp_return"]]
    results = await client.read_entities_batched(entities)

    assert unit.read_events == [
        ReadEvent("input", 20, 4),  # block read
        ReadEvent("input", 20, 2),  # individual read
        ReadEvent("input", 22, 2),  # individual read
    ]
    assert round(results["temp_supply"], 1) == 24.5
    assert round(results["temp_return"], 1) == 25.0
    assert client.is_connected is True


@pytest.mark.asyncio
async def test_batched_short_successful_response_falls_back_to_individual_reads(
    client, unit
):
    """A well-formed but too-short block response degrades gracefully.

    A device can answer a block read with fewer registers/bits than the
    requested count (a malformed-but-"successful" response). Decoding it
    must not raise IndexError; since get_all_data() is polled by HA core
    every 15s via this same batching path, such a response must degrade the
    same way a failed block does: fall back to individual reads.
    """
    unit.input[20] = float32_regs(24.5) + float32_regs(25.0)
    # Block read: only 2 registers come back for a block that needs 4
    script_reads(unit, "read_input_registers", float32_regs(24.5))

    entities = [SENSORS["temp_supply"], SENSORS["temp_return"]]
    results = await client.read_entities_batched(entities)

    assert len(unit.read_events) == 3
    assert round(results["temp_supply"], 1) == 24.5
    assert round(results["temp_return"], 1) == 25.0


@pytest.mark.asyncio
async def test_get_all_entities_uses_batched_reads(client, unit):
    """get_all_entities reads all entities in a handful of transactions."""
    results = await client.get_all_entities()

    expected_keys = set(SENSORS) | set(BINARY_SENSORS) | set(SWITCHES)
    assert set(results) == expected_keys
    assert len(unit.read_events) <= 15


@pytest.mark.asyncio
async def test_get_all_data_uses_batched_reads(client, unit):
    """get_all_data (used by HA core, polled every 15s) reads via block reads.

    A per-field implementation needs ~59 transactions (23 core sensors + 37
    binary sensors). get_all_data() uses the same batched block-read
    infrastructure as get_all_entities(), landing in a handful instead.
    """
    state = await client.get_all_data()

    assert state is not None
    assert len(unit.read_events) <= 15
