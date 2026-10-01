"""read_all_* helpers must match per-entity reads while batching requests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from python_qube_heatpump import QubeClient
from python_qube_heatpump.entities import BINARY_SENSORS, SENSORS, SWITCHES


def _fake_device(mock_instance):
    """Serve a fixed, address-dependent register and bit map."""

    def registers(address, count=1, **kwargs):
        resp = MagicMock()
        resp.isError.return_value = False
        # Varied words so float32/int16/uint32 decoding is exercised
        resp.registers = [
            (a * 7919 + 0x4100) & 0xFFFF for a in range(address, address + count)
        ]
        return resp

    def bits(address, count=1, **kwargs):
        resp = MagicMock()
        resp.isError.return_value = False
        resp.bits = [
            bool((a * 2654435761) & 4) for a in range(address, address + count)
        ]
        return resp

    mock_instance.read_input_registers = AsyncMock(side_effect=registers)
    mock_instance.read_holding_registers = AsyncMock(side_effect=registers)
    mock_instance.read_coils = AsyncMock(side_effect=bits)
    mock_instance.read_discrete_inputs = AsyncMock(side_effect=bits)


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


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and a != a and b != b:
        return True  # both NaN
    return a == b and type(a) is type(b)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "table"),
    [
        ("read_all_sensors", SENSORS),
        ("read_all_binary_sensors", BINARY_SENSORS),
        ("read_all_switches", SWITCHES),
    ],
)
async def test_read_all_matches_single_reads_with_fewer_requests(
    mock_modbus_client, method, table
):
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    _fake_device(mock_instance)

    expected = {key: await client.read_entity(ent) for key, ent in table.items()}
    single_reads = _total_reads(mock_instance)

    mock_instance.reset_mock()
    _fake_device(mock_instance)
    result = await getattr(client, method)()

    assert list(result) == list(table)
    mismatched = [k for k in table if not _same(result[k], expected[k])]
    assert mismatched == []
    assert _total_reads(mock_instance) < single_reads
    assert _total_reads(mock_instance) == len(client._plan_blocks(table.values()))
