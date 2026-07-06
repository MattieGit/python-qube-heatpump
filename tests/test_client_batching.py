"""Tests for batched block reads in QubeClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from python_qube_heatpump import QubeClient
from python_qube_heatpump.entities import BINARY_SENSORS, SENSORS, SWITCHES
from python_qube_heatpump.entities.base import (
    DataType,
    EntityDef,
    InputType,
    Platform,
)


def _bit_response(bits):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.bits = bits
    return resp


def _register_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = registers
    return resp


def _float32_regs(value):
    import struct

    int_val = struct.unpack(">I", struct.pack(">f", value))[0]
    return [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]


@pytest.mark.asyncio
async def test_batched_discrete_inputs_single_transaction(mock_modbus_client):
    """Adjacent discrete inputs are read in one block transaction."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.read_discrete_inputs = AsyncMock(
        return_value=_bit_response([True, False, True])
    )
    client._client = mock_instance

    entities = [
        BINARY_SENSORS["dout_srcpmp_val"],  # address 0
        BINARY_SENSORS["dout_usrpmp_val"],  # address 1
        BINARY_SENSORS["dout_fourwayvlv_val"],  # address 2
    ]
    results = await client.read_entities_batched(entities)

    assert mock_instance.read_discrete_inputs.call_count == 1
    call = mock_instance.read_discrete_inputs.call_args
    assert call.args[0] == 0
    assert call.kwargs["count"] >= 3
    assert results == {
        "dout_srcpmp_val": True,
        "dout_usrpmp_val": False,
        "dout_fourwayvlv_val": True,
    }


@pytest.mark.asyncio
async def test_batched_input_registers_decode_float32(mock_modbus_client):
    """Adjacent float32 input registers decode correctly from one block."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    regs = _float32_regs(24.5) + _float32_regs(25.0)
    mock_instance.read_input_registers = AsyncMock(
        return_value=_register_response(regs)
    )
    client._client = mock_instance

    entities = [
        SENSORS["temp_supply"],  # address 20, float32
        SENSORS["temp_return"],  # address 22, float32
    ]
    results = await client.read_entities_batched(entities)

    assert mock_instance.read_input_registers.call_count == 1
    call = mock_instance.read_input_registers.call_args
    assert call.args[0] == 20
    assert call.kwargs["count"] == 4
    assert round(results["temp_supply"], 1) == 24.5
    assert round(results["temp_return"], 1) == 25.0


@pytest.mark.asyncio
async def test_batched_far_apart_registers_split_into_blocks(mock_modbus_client):
    """Registers far apart are read in separate block transactions."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.read_holding_registers = AsyncMock(
        return_value=_register_response(_float32_regs(1.0))
    )
    client._client = mock_instance

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
    await client.read_entities_batched([ent_a, ent_b])

    assert mock_instance.read_holding_registers.call_count == 2


@pytest.mark.asyncio
async def test_batched_block_failure_falls_back_to_individual_reads(
    mock_modbus_client,
):
    """If a block read fails, entities in it are read individually."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.read_input_registers = AsyncMock(
        side_effect=[
            OSError("No response received after 3 retries"),  # block read
            _register_response(_float32_regs(24.5)),  # individual read
            _register_response(_float32_regs(25.0)),  # individual read
        ]
    )
    client._client = mock_instance

    entities = [SENSORS["temp_supply"], SENSORS["temp_return"]]
    results = await client.read_entities_batched(entities)

    assert mock_instance.read_input_registers.call_count == 3
    assert round(results["temp_supply"], 1) == 24.5
    assert round(results["temp_return"], 1) == 25.0


@pytest.mark.asyncio
async def test_get_all_entities_uses_batched_reads(mock_modbus_client):
    """get_all_entities reads all entities in a handful of transactions."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    def _bits(address, count=1, **kwargs):
        return _bit_response([False] * count)

    def _regs(address, count=1, **kwargs):
        return _register_response([0] * count)

    mock_instance.read_coils = AsyncMock(side_effect=_bits)
    mock_instance.read_discrete_inputs = AsyncMock(side_effect=_bits)
    mock_instance.read_input_registers = AsyncMock(side_effect=_regs)
    mock_instance.read_holding_registers = AsyncMock(side_effect=_regs)
    client._client = mock_instance

    results = await client.get_all_entities()

    expected_keys = set(SENSORS) | set(BINARY_SENSORS) | set(SWITCHES)
    assert set(results) == expected_keys
    total_calls = (
        mock_instance.read_coils.call_count
        + mock_instance.read_discrete_inputs.call_count
        + mock_instance.read_input_registers.call_count
        + mock_instance.read_holding_registers.call_count
    )
    assert total_calls <= 15
