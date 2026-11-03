"""read_all_* helpers must match per-entity reads while batching requests."""

import pytest

from python_qube_heatpump.entities import BINARY_SENSORS, SENSORS, SWITCHES

# Every address the entity tables use, plus room for a 32-bit value
_ADDRESSES = range(
    max(e.address for t in (SENSORS, BINARY_SENSORS, SWITCHES) for e in t.values()) + 2
)


def _fake_device(unit):
    """Serve a fixed, address-dependent register and bit map."""
    # Varied words so float32/int16/uint32 decoding is exercised
    registers = [(a * 7919 + 0x4100) & 0xFFFF for a in _ADDRESSES]
    bits = [bool((a * 2654435761) & 4) for a in _ADDRESSES]
    unit.input[0] = registers
    unit.holding[0] = registers
    unit.coil[0] = bits
    unit.discrete[0] = bits


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
    client, unit, method, table
):
    _fake_device(unit)

    expected = {key: await client.read_entity(ent) for key, ent in table.items()}
    single_reads = len(unit.read_events)

    unit.read_events.clear()
    result = await getattr(client, method)()

    assert list(result) == list(table)
    mismatched = [k for k in table if not _same(result[k], expected[k])]
    assert mismatched == []
    assert len(unit.read_events) < single_reads
    assert len(unit.read_events) == len(client._plan_blocks(table.values()))
