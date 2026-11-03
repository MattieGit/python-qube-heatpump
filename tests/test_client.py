"""Test the Qube Heat Pump client."""

import logging
from unittest.mock import AsyncMock

import pytest
from helpers import float32_regs
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTcpParams,
)
from modbus_connection.mock import ReadEvent, WriteEvent

from python_qube_heatpump import QubeClient, const
from python_qube_heatpump.entities import BINARY_SENSORS


@pytest.mark.asyncio
async def test_connect(connection_factory):
    """An owned connection targets host:port and connects."""
    client = QubeClient("1.2.3.4", 502)
    connection_factory.assert_called_once_with(
        ModbusTcpParams(host="1.2.3.4", port=502), timeout=QubeClient.TIMEOUT
    )
    assert client.is_connected is False
    assert await client.connect() is True
    assert client.is_connected is True


@pytest.mark.asyncio
async def test_read_value(client, unit):
    """Test reading values."""
    # 24.5 = 0x41C40000 -> Big Endian word order (ABCD)
    # regs[0]=0x41C4=16836 (MSW), regs[1]=0x0000=0 (LSW)
    unit.holding[10] = [16836, 0]

    # definition = (address, reg_type, data_type, scale, offset)
    definition = (10, const.ModbusType.HOLDING, const.DataType.FLOAT32, None, None)

    result = await client.read_value(definition)

    # Verify result is approximately 24.5
    assert result is not None
    assert round(result, 1) == 24.5
    assert unit.read_events == [ReadEvent("holding", 10, 2)]


@pytest.mark.asyncio
async def test_read_value_int16(client, unit):
    """Test reading INT16 value."""
    # -10 = 0xFFF6 = 65526
    unit.input[20] = 65526

    definition = (20, const.ModbusType.INPUT, const.DataType.INT16, None, None)

    result = await client.read_value(definition)
    assert result == -10
    assert unit.read_events == [ReadEvent("input", 20, 1)]


@pytest.mark.asyncio
async def test_read_sensor(client, unit):
    """Test reading a sensor by key."""
    # temp_supply (FLOAT32) = 35.5°C: 0x420E0000 -> [0x420E=16910, 0]
    unit.input[20] = [16910, 0]

    result = await client.read_sensor("temp_supply")
    assert result is not None
    assert round(result, 1) == 35.5


@pytest.mark.asyncio
async def test_read_sensor_unknown_key(client, unit):
    """Test reading a sensor with unknown key returns None."""
    result = await client.read_sensor("unknown_sensor")
    assert result is None
    assert unit.read_events == []


@pytest.mark.asyncio
async def test_read_binary_sensor(client, unit):
    """Test reading a binary sensor by key."""
    unit.discrete[0] = True

    result = await client.read_binary_sensor("dout_srcpmp_val")
    assert result is True
    assert unit.read_events == [ReadEvent("discrete", 0, 1)]


@pytest.mark.asyncio
async def test_read_binary_sensor_coil(client, unit):
    """Test reading a coil-based binary sensor."""
    unit.coil[19] = False

    result = await client.read_binary_sensor("bms_demand")
    assert result is False
    assert unit.read_events == [ReadEvent("coil", 19, 1)]


@pytest.mark.asyncio
async def test_read_switch(client, unit):
    """Test reading a switch by key."""
    unit.coil[22] = True

    result = await client.read_switch("bms_summerwinter")
    assert result is True


@pytest.mark.asyncio
async def test_read_switch_unknown_key(client, unit):
    """Test reading a switch with unknown key returns None."""
    result = await client.read_switch("unknown_switch")
    assert result is None
    assert unit.read_events == []


@pytest.mark.asyncio
async def test_write_switch(client, unit, writes):
    """Test writing a switch."""
    result = await client.write_switch("bms_summerwinter", True)
    assert result is True
    assert writes == [WriteEvent("coil", 22, [True], 0x05)]
    assert unit.coil[22] is True


@pytest.mark.asyncio
async def test_write_switch_unknown_key(client, writes):
    """Test writing a switch with unknown key returns False."""
    result = await client.write_switch("unknown_switch", True)
    assert result is False
    assert writes == []


@pytest.mark.asyncio
async def test_write_setpoint(client, unit, writes):
    """Test writing a setpoint value."""
    # setpoint_dhw is writable; 55.0 = 0x425C0000
    result = await client.write_setpoint("setpoint_dhw", 55.0)
    assert result is True
    assert writes == [WriteEvent("holding", 173, [0x425C, 0], 0x10)]
    assert [unit.holding[173], unit.holding[174]] == float32_regs(55.0)


@pytest.mark.asyncio
async def test_write_setpoint_non_writable(client, writes):
    """Test writing a non-writable sensor returns False."""
    # temp_supply is not writable
    result = await client.write_setpoint("temp_supply", 35.0)
    assert result is False
    assert writes == []


@pytest.mark.asyncio
async def test_write_setpoint_unknown_key(client, writes):
    """Test writing a setpoint with unknown key returns False."""
    result = await client.write_setpoint("unknown_sensor", 50.0)
    assert result is False
    assert writes == []


@pytest.mark.asyncio
async def test_get_software_version(client, unit):
    """Test reading software version."""
    # 2.15 ~ 0x4009999A -> regs[0]=0x4009=16393, regs[1]=0x999A=39322
    unit.input[77] = [16393, 39322]

    result = await client.async_get_software_version()
    assert result == "2.15"


@pytest.mark.asyncio
async def test_get_software_version_zero(client, unit):
    """Test an unpopulated register (reads 0) returns None, not "0.00"."""
    unit.input[77] = [0, 0]

    result = await client.async_get_software_version()
    assert result is None


@pytest.mark.asyncio
async def test_get_software_version_error(client, unit):
    """Test software version returns None on error."""
    unit.fail_read(77, IllegalDataAddressError(), register_type="input")

    result = await client.async_get_software_version()
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("registers", "expected"),
    [
        pytest.param([16393, 39322], True, id="version"),
        pytest.param([0, 0], True, id="unpopulated"),
    ],
)
async def test_verify_device(client, unit, registers, expected):
    """Test any readable register 77 value verifies the device, including 0."""
    unit.input[77] = registers

    assert await client.async_verify_device() is expected


@pytest.mark.asyncio
async def test_verify_device_error(client, unit):
    """Test a failed register 77 read does not verify the device."""
    unit.fail_read(77, IllegalDataAddressError(), register_type="input")

    assert await client.async_verify_device() is False


@pytest.mark.asyncio
async def test_ensure_connected_reconnects(owned_client, owned_connection, mocker):
    """Test _ensure_connected reconnects when disconnected."""
    connects = mocker.spy(owned_connection, "_connect_client")

    assert await owned_client._ensure_connected() is True
    assert owned_client.is_connected is True
    assert connects.call_count == 1


@pytest.mark.asyncio
async def test_ensure_connected_skips_when_connected(
    owned_client, owned_connection, mocker
):
    """Test _ensure_connected does nothing when already connected."""
    assert await owned_client.connect() is True
    connect = mocker.spy(owned_connection, "connect")

    assert await owned_client._ensure_connected() is True
    connect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_backoff(owned_client, owned_connection, monkeypatch):
    """Test _ensure_connected applies exponential backoff on failure."""
    monkeypatch.setattr(
        owned_connection,
        "connect",
        AsyncMock(side_effect=ModbusConnectionError("refused")),
    )

    # First failure — backoff starts at 1s
    assert await owned_client._ensure_connected() is False
    assert owned_client.is_connected is False
    assert owned_client._backoff_seconds == 1.0

    # While backing off, no new attempt is made
    assert await owned_client._ensure_connected() is False
    assert owned_connection.connect.await_count == 1

    # Second failure — backoff doubles to 2s
    owned_client._next_connect_at = 0  # bypass wait for test
    assert await owned_client._ensure_connected() is False
    assert owned_client._backoff_seconds == 2.0


@pytest.mark.asyncio
async def test_ensure_connected_backoff_resets_on_success(owned_client):
    """Test backoff resets after successful connect."""
    owned_client._backoff_seconds = 16.0

    assert await owned_client._ensure_connected() is True
    assert owned_client.is_connected is True
    assert owned_client._backoff_seconds == 0.0


@pytest.mark.asyncio
async def test_get_all_data_auto_reconnects(owned_client, owned_connection, mocker):
    """Test get_all_data connects before reading."""
    connects = mocker.spy(owned_connection, "_connect_client")
    assert owned_client.is_connected is False

    state = await owned_client.get_all_data()
    assert state is not None
    assert connects.call_count == 1
    assert owned_client.is_connected is True


@pytest.mark.asyncio
async def test_clamp_monotonic_basic(client):
    """Test clamp_monotonic prevents decreases."""
    # First value establishes baseline
    assert client.clamp_monotonic("energy", 100.0) == 100.0
    # Increase passes through
    assert client.clamp_monotonic("energy", 150.0) == 150.0
    # Decrease gets clamped to previous
    assert client.clamp_monotonic("energy", 50.0) == 150.0
    # Recovery passes through
    assert client.clamp_monotonic("energy", 160.0) == 160.0


@pytest.mark.asyncio
async def test_clamp_monotonic_none_and_nan(client):
    """Test clamp_monotonic passes through None and NaN."""
    # None passes through
    assert client.clamp_monotonic("energy", None) is None

    # Establish baseline
    assert client.clamp_monotonic("energy", 100.0) == 100.0

    # None doesn't update cache
    assert client.clamp_monotonic("energy", None) is None
    assert client.monotonic_cache["energy"] == 100.0

    # NaN doesn't update cache
    result = client.clamp_monotonic("energy", float("nan"))
    assert result != result  # NaN != NaN
    assert client.monotonic_cache["energy"] == 100.0


@pytest.mark.asyncio
async def test_clamp_monotonic_independent_keys(client):
    """Test clamp_monotonic tracks keys independently."""
    client.clamp_monotonic("electric", 100.0)
    client.clamp_monotonic("thermic", 200.0)

    # Decrease in one doesn't affect the other
    assert client.clamp_monotonic("electric", 50.0) == 100.0
    assert client.clamp_monotonic("thermic", 250.0) == 250.0


@pytest.mark.asyncio
async def test_monotonic_cache_property(client):
    """Test monotonic_cache can be get/set for persistence."""
    # Cache starts empty
    assert client.monotonic_cache == {}

    # Set cache (e.g. restored from disk)
    client.monotonic_cache = {"energy": 100.0, "thermic": 200.0}
    assert client.monotonic_cache == {"energy": 100.0, "thermic": 200.0}

    # Clamping uses the restored cache
    assert client.clamp_monotonic("energy", 50.0) == 100.0
    assert client.clamp_monotonic("thermic", 250.0) == 250.0

    # Setting cache makes a copy
    original = {"energy": 300.0}
    client.monotonic_cache = original
    original["energy"] = 999.0
    assert client.monotonic_cache["energy"] == 300.0


@pytest.mark.asyncio
async def test_get_all_data_applies_clamping(client, unit):
    """Test get_all_data uses clamp_monotonic for energy counters."""
    unit.input[69] = float32_regs(120.0)  # energy_total_electric
    unit.input[71] = float32_regs(480.0)  # energy_total_thermic

    state = await client.get_all_data()
    assert state is not None
    # Energy values stored in cache
    assert client.monotonic_cache.get("energy_total_electric") == 120.0
    assert client.monotonic_cache.get("energy_total_thermic") == 480.0

    # A small drop is clamped to the cached maximum
    unit.input[69] = float32_regs(119.5)
    state = await client.get_all_data()
    assert state is not None
    assert state.energy_total_electric == 120.0


@pytest.mark.asyncio
async def test_get_sg_ready_mode(client, unit):
    """Test reading SG Ready mode from coil bits."""
    # Both coils come back in one block read: A=False, B=True -> "plus"
    unit.coil[65] = [False, True]

    result = await client.get_sg_ready_mode()
    assert result == "plus"


@pytest.mark.asyncio
async def test_get_sg_ready_mode_all_modes(client, unit):
    """Test all SG Ready mode combinations."""
    cases = [
        ((False, False), "off"),
        ((True, False), "block"),
        ((False, True), "plus"),
        ((True, True), "max"),
    ]
    for (bit_a, bit_b), expected_mode in cases:
        unit.coil[65] = [bit_a, bit_b]

        result = await client.get_sg_ready_mode()
        assert result == expected_mode, (
            f"Expected {expected_mode} for bits ({bit_a}, {bit_b})"
        )


@pytest.mark.asyncio
async def test_get_sg_ready_mode_read_error(client, unit):
    """Test SG Ready mode returns None on read error."""
    unit.fail_read(65, IllegalDataAddressError(), register_type="coil")

    result = await client.get_sg_ready_mode()
    assert result is None


@pytest.mark.asyncio
async def test_set_sg_ready_mode(client, unit, writes):
    """Test setting SG Ready mode writes both coils in one request."""
    result = await client.set_sg_ready_mode("plus")
    assert result is True

    # "plus" = (False, True) -> A=False (coil 65), B=True (coil 66)
    assert writes == [WriteEvent("coil", 65, [False, True], 0x0F)]
    assert (unit.coil[65], unit.coil[66]) == (False, True)


@pytest.mark.asyncio
async def test_set_sg_ready_mode_unknown(client, writes):
    """Test setting unknown SG Ready mode returns False."""
    result = await client.set_sg_ready_mode("turbo")
    assert result is False
    assert writes == []


@pytest.mark.asyncio
async def test_read_entity_failure_logs_warning_once_then_debug(client, unit, caplog):
    """Transient read failures log WARNING on first occurrence, DEBUG after."""
    unit.fail_read(0, OSError("No response"), register_type="discrete")

    entity = BINARY_SENSORS["dout_srcpmp_val"]

    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        assert await client.read_entity(entity) is None
        assert await client.read_entity(entity) is None

    records = [r for r in caplog.records if "dout_srcpmp_val" in r.getMessage()]
    assert len(records) == 2
    assert records[0].levelno == logging.WARNING
    assert records[1].levelno == logging.DEBUG
    assert not any(r.levelno == logging.ERROR for r in records)


@pytest.mark.asyncio
async def test_read_entity_warns_again_per_entity(client, unit, caplog):
    """The warn-once tracking is per entity, not global."""
    unit.fail_requests(OSError("No response"))

    with caplog.at_level(logging.DEBUG, logger="python_qube_heatpump.client"):
        await client.read_entity(BINARY_SENSORS["dout_srcpmp_val"])
        await client.read_entity(BINARY_SENSORS["dout_usrpmp_val"])

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2


@pytest.mark.asyncio
async def test_clamp_monotonic_reset_detected_after_confirmation(client):
    """A drop larger than the reset threshold becomes the new baseline once confirmed."""
    assert client.clamp_monotonic("energy", 1000.0) == 1000.0

    # First two low reads are still clamped (could be a transient glitch)
    assert client.clamp_monotonic("energy", 3.0) == 1000.0
    assert client.clamp_monotonic("energy", 3.1) == 1000.0
    # Third consecutive low read confirms the reset
    assert client.clamp_monotonic("energy", 3.2) == 3.2
    assert client.monotonic_cache["energy"] == 3.2
    # Counting resumes from the new baseline
    assert client.clamp_monotonic("energy", 3.5) == 3.5


@pytest.mark.asyncio
async def test_clamp_monotonic_reset_logs_warning(client, caplog):
    """Confirming a reset logs a warning naming the key."""
    client.clamp_monotonic("energy_total_thermic", 500.0)
    with caplog.at_level(logging.WARNING):
        for _ in range(QubeClient.MONOTONIC_RESET_CONFIRM_READS):
            client.clamp_monotonic("energy_total_thermic", 0.0)
    assert "Counter reset detected" in caplog.text
    assert "energy_total_thermic" in caplog.text


@pytest.mark.asyncio
async def test_clamp_monotonic_transient_glitch_does_not_reset(client):
    """A single low read followed by recovery must not become a new baseline."""
    client.clamp_monotonic("energy", 1000.0)

    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    # Recovery cancels the pending reset
    assert client.clamp_monotonic("energy", 1000.2) == 1000.2
    # A fresh low read starts counting from scratch again
    assert client.clamp_monotonic("energy", 0.0) == 1000.2
    assert client.clamp_monotonic("energy", 0.0) == 1000.2
    assert client.monotonic_cache["energy"] == 1000.2


@pytest.mark.asyncio
async def test_clamp_monotonic_sub_threshold_jitter_still_clamped(client):
    """Drops smaller than the threshold are jitter and stay clamped forever."""
    client.clamp_monotonic("energy", 1000.0)
    for _ in range(10):
        assert client.clamp_monotonic("energy", 999.5) == 1000.0
    assert client.monotonic_cache["energy"] == 1000.0
    # Jitter reads do not count towards reset confirmation
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    assert client.clamp_monotonic("energy", 999.5) == 1000.0
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
    assert client.monotonic_cache["energy"] == 1000.0


@pytest.mark.asyncio
async def test_clamp_monotonic_custom_threshold(client):
    """The reset threshold can be overridden per call."""
    client.clamp_monotonic("hours", 100.0, reset_threshold=10.0)
    # A 5-unit drop is below the custom threshold: clamped, never a reset
    for _ in range(5):
        assert client.clamp_monotonic("hours", 95.0, reset_threshold=10.0) == 100.0
    # A 50-unit drop is a reset
    for _ in range(QubeClient.MONOTONIC_RESET_CONFIRM_READS - 1):
        assert client.clamp_monotonic("hours", 50.0, reset_threshold=10.0) == 100.0
    assert client.clamp_monotonic("hours", 50.0, reset_threshold=10.0) == 50.0


@pytest.mark.asyncio
async def test_clear_monotonic_cache(client):
    """Clearing the cache forgets baselines and pending resets."""
    client.clamp_monotonic("energy", 1000.0)
    client.clamp_monotonic("energy", 0.0)  # pending reset
    client.clear_monotonic_cache()
    assert client.monotonic_cache == {}
    # Next read is accepted as a fresh baseline
    assert client.clamp_monotonic("energy", 5.0) == 5.0


@pytest.mark.asyncio
async def test_monotonic_cache_setter_discards_pending_resets(client):
    """Restoring a cache from disk resets the reset-confirmation counters."""
    client.clamp_monotonic("energy", 1000.0)
    client.clamp_monotonic("energy", 0.0)
    client.clamp_monotonic("energy", 0.0)
    client.monotonic_cache = {"energy": 1000.0}
    # Only one low read so far after the restore: still clamped
    assert client.clamp_monotonic("energy", 0.0) == 1000.0
