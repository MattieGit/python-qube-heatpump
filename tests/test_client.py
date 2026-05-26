"""Test the Qube Heat Pump client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from python_qube_heatpump import QubeClient


@pytest.mark.asyncio
async def test_connect(mock_modbus_client):
    """Test connection."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connect.return_value = True
    mock_instance.connected = False
    assert await client.connect() is True
    mock_modbus_client.assert_called_with("1.2.3.4", port=502)


@pytest.mark.asyncio
async def test_read_value(mock_modbus_client):
    """Test reading values."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connected = True

    # Mock response for reading holding registers (FLOAT32)
    # 24.5 = 0x41C40000 -> Big Endian word order (ABCD)
    # Logic in client.py: int_val = (regs[0] << 16) | regs[1]
    # regs[0]=0x41C4=16836 (MSW), regs[1]=0x0000=0 (LSW)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [16836, 0]

    mock_instance.read_holding_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    # Test reading a FLOAT32 holding register
    # definition = (address, reg_type, data_type, scale, offset)
    # We use a dummy definition
    from python_qube_heatpump import const

    definition = (10, const.ModbusType.HOLDING, const.DataType.FLOAT32, None, None)

    result = await client.read_value(definition)

    # Verify result is approximately 24.5
    assert result is not None
    assert round(result, 1) == 24.5

    mock_instance.read_holding_registers.assert_called_once()


@pytest.mark.asyncio
async def test_read_value_int16(mock_modbus_client):
    """Test reading INT16 value."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for -10 (0xFFF6 = 65526)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [65526]

    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    from python_qube_heatpump import const

    definition = (20, const.ModbusType.INPUT, const.DataType.INT16, None, None)

    result = await client.read_value(definition)
    assert result == -10


@pytest.mark.asyncio
async def test_read_sensor(mock_modbus_client):
    """Test reading a sensor by key."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for temp_supply (FLOAT32) = 35.5°C
    # 35.5 = 0x420E0000 -> Big Endian word order (ABCD)
    # regs[0]=0x420E=16910 (MSW), regs[1]=0x0000=0 (LSW)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [16910, 0]

    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.read_sensor("temp_supply")
    assert result is not None
    assert round(result, 1) == 35.5


@pytest.mark.asyncio
async def test_read_sensor_unknown_key(mock_modbus_client):
    """Test reading a sensor with unknown key returns None."""
    client = QubeClient("1.2.3.4", 502)
    result = await client.read_sensor("unknown_sensor")
    assert result is None


@pytest.mark.asyncio
async def test_read_binary_sensor(mock_modbus_client):
    """Test reading a binary sensor by key."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for discrete input (True)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.bits = [True]

    mock_instance.read_discrete_inputs = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.read_binary_sensor("dout_srcpmp_val")
    assert result is True


@pytest.mark.asyncio
async def test_read_binary_sensor_coil(mock_modbus_client):
    """Test reading a coil-based binary sensor."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for coil (False)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.bits = [False]

    mock_instance.read_coils = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.read_binary_sensor("bms_demand")
    assert result is False


@pytest.mark.asyncio
async def test_read_switch(mock_modbus_client):
    """Test reading a switch by key."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for coil (True)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.bits = [True]

    mock_instance.read_coils = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.read_switch("bms_summerwinter")
    assert result is True


@pytest.mark.asyncio
async def test_read_switch_unknown_key(mock_modbus_client):
    """Test reading a switch with unknown key returns None."""
    client = QubeClient("1.2.3.4", 502)
    result = await client.read_switch("unknown_switch")
    assert result is None


@pytest.mark.asyncio
async def test_write_switch(mock_modbus_client):
    """Test writing a switch."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    mock_resp = MagicMock()
    mock_resp.isError.return_value = False

    mock_instance.write_coil = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.write_switch("bms_summerwinter", True)
    assert result is True
    mock_instance.write_coil.assert_called_once()


@pytest.mark.asyncio
async def test_write_switch_unknown_key(mock_modbus_client):
    """Test writing a switch with unknown key returns False."""
    client = QubeClient("1.2.3.4", 502)
    result = await client.write_switch("unknown_switch", True)
    assert result is False


@pytest.mark.asyncio
async def test_write_setpoint(mock_modbus_client):
    """Test writing a setpoint value."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    mock_resp = MagicMock()
    mock_resp.isError.return_value = False

    mock_instance.write_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    # setpoint_dhw is writable
    result = await client.write_setpoint("setpoint_dhw", 55.0)
    assert result is True
    mock_instance.write_registers.assert_called_once()


@pytest.mark.asyncio
async def test_write_setpoint_non_writable(mock_modbus_client):
    """Test writing a non-writable sensor returns False."""
    client = QubeClient("1.2.3.4", 502)
    # temp_supply is not writable
    result = await client.write_setpoint("temp_supply", 35.0)
    assert result is False


@pytest.mark.asyncio
async def test_write_setpoint_unknown_key(mock_modbus_client):
    """Test writing a setpoint with unknown key returns False."""
    client = QubeClient("1.2.3.4", 502)
    result = await client.write_setpoint("unknown_sensor", 50.0)
    assert result is False


@pytest.mark.asyncio
async def test_get_software_version(mock_modbus_client):
    """Test reading software version."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    # Mock response for version 2.15 as FLOAT32
    # 2.15 ~ 0x4009999A -> regs[0]=0x4009=16393, regs[1]=0x999A=39322
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [16393, 39322]

    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.async_get_software_version()
    assert result is not None
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_software_version_error(mock_modbus_client):
    """Test software version returns None on error."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value

    mock_resp = MagicMock()
    mock_resp.isError.return_value = True

    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    client._client = mock_instance

    result = await client.async_get_software_version()
    assert result is None


@pytest.mark.asyncio
async def test_ensure_connected_reconnects(mock_modbus_client):
    """Test _ensure_connected reconnects when disconnected."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connect.return_value = True
    client._client = mock_instance
    client._connected = False

    await client._ensure_connected()
    assert client._connected is True
    mock_instance.connect.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_connected_skips_when_connected(mock_modbus_client):
    """Test _ensure_connected does nothing when already connected."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    client._connected = True

    await client._ensure_connected()
    mock_instance.connect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_backoff(mock_modbus_client):
    """Test _ensure_connected applies exponential backoff on failure."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connect.return_value = False
    client._client = mock_instance
    client._connected = False

    # First failure — backoff starts at 1s
    await client._ensure_connected()
    assert client._connected is False
    assert client._backoff_seconds == 1.0

    # Second failure — backoff doubles to 2s
    client._next_connect_at = 0  # bypass wait for test
    await client._ensure_connected()
    assert client._backoff_seconds == 2.0


@pytest.mark.asyncio
async def test_ensure_connected_backoff_resets_on_success(mock_modbus_client):
    """Test backoff resets after successful connect."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    client._connected = False
    client._backoff_seconds = 16.0

    mock_instance.connect.return_value = True
    await client._ensure_connected()
    assert client._connected is True
    assert client._backoff_seconds == 0.0


@pytest.mark.asyncio
async def test_get_all_data_auto_reconnects(mock_modbus_client):
    """Test get_all_data calls _ensure_connected before reading."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connect.return_value = True
    client._client = mock_instance
    client._connected = False

    # Mock successful register reads
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [0, 0]
    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    mock_instance.read_holding_registers = AsyncMock(return_value=mock_resp)

    state = await client.get_all_data()
    assert state is not None
    # Verify connect was called (auto-reconnect happened)
    mock_instance.connect.assert_called_once()


@pytest.mark.asyncio
async def test_clamp_monotonic_basic(mock_modbus_client):
    """Test clamp_monotonic prevents decreases."""
    client = QubeClient("1.2.3.4", 502)

    # First value establishes baseline
    assert client.clamp_monotonic("energy", 100.0) == 100.0
    # Increase passes through
    assert client.clamp_monotonic("energy", 150.0) == 150.0
    # Decrease gets clamped to previous
    assert client.clamp_monotonic("energy", 50.0) == 150.0
    # Recovery passes through
    assert client.clamp_monotonic("energy", 160.0) == 160.0


@pytest.mark.asyncio
async def test_clamp_monotonic_none_and_nan(mock_modbus_client):
    """Test clamp_monotonic passes through None and NaN."""
    client = QubeClient("1.2.3.4", 502)

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
async def test_clamp_monotonic_independent_keys(mock_modbus_client):
    """Test clamp_monotonic tracks keys independently."""
    client = QubeClient("1.2.3.4", 502)

    client.clamp_monotonic("electric", 100.0)
    client.clamp_monotonic("thermic", 200.0)

    # Decrease in one doesn't affect the other
    assert client.clamp_monotonic("electric", 50.0) == 100.0
    assert client.clamp_monotonic("thermic", 250.0) == 250.0


@pytest.mark.asyncio
async def test_monotonic_cache_property(mock_modbus_client):
    """Test monotonic_cache can be get/set for persistence."""
    client = QubeClient("1.2.3.4", 502)

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
async def test_get_all_data_applies_clamping(mock_modbus_client):
    """Test get_all_data uses clamp_monotonic for energy counters."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    client._connected = True

    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [0, 0]
    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    mock_instance.read_holding_registers = AsyncMock(return_value=mock_resp)

    state = await client.get_all_data()
    assert state is not None
    # Energy values stored in cache
    assert client.monotonic_cache.get("energy_total_electric") == 0.0
    assert client.monotonic_cache.get("energy_total_thermic") == 0.0


@pytest.mark.asyncio
async def test_get_sg_ready_mode(mock_modbus_client):
    """Test reading SG Ready mode from coil bits."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance

    # Mock coil reads: A=False, B=True -> "plus"
    mock_resp_a = MagicMock()
    mock_resp_a.isError.return_value = False
    mock_resp_a.bits = [False]

    mock_resp_b = MagicMock()
    mock_resp_b.isError.return_value = False
    mock_resp_b.bits = [True]

    mock_instance.read_coils = AsyncMock(side_effect=[mock_resp_a, mock_resp_b])

    result = await client.get_sg_ready_mode()
    assert result == "plus"


@pytest.mark.asyncio
async def test_get_sg_ready_mode_all_modes(mock_modbus_client):
    """Test all SG Ready mode combinations."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance

    cases = [
        ((False, False), "off"),
        ((True, False), "block"),
        ((False, True), "plus"),
        ((True, True), "max"),
    ]
    for (bit_a, bit_b), expected_mode in cases:
        resp_a = MagicMock()
        resp_a.isError.return_value = False
        resp_a.bits = [bit_a]
        resp_b = MagicMock()
        resp_b.isError.return_value = False
        resp_b.bits = [bit_b]
        mock_instance.read_coils = AsyncMock(side_effect=[resp_a, resp_b])

        result = await client.get_sg_ready_mode()
        assert result == expected_mode, (
            f"Expected {expected_mode} for bits ({bit_a}, {bit_b})"
        )


@pytest.mark.asyncio
async def test_get_sg_ready_mode_read_error(mock_modbus_client):
    """Test SG Ready mode returns None on read error."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance

    mock_resp = MagicMock()
    mock_resp.isError.return_value = True
    mock_instance.read_coils = AsyncMock(return_value=mock_resp)

    result = await client.get_sg_ready_mode()
    assert result is None


@pytest.mark.asyncio
async def test_set_sg_ready_mode(mock_modbus_client):
    """Test setting SG Ready mode writes both coils."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance

    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_instance.write_coil = AsyncMock(return_value=mock_resp)

    result = await client.set_sg_ready_mode("plus")
    assert result is True

    # "plus" = (False, True) -> A=False, B=True
    calls = mock_instance.write_coil.call_args_list
    assert len(calls) == 2
    assert calls[0].args == (65, False)  # bms_sgready_a address
    assert calls[1].args == (66, True)  # bms_sgready_b address


@pytest.mark.asyncio
async def test_set_sg_ready_mode_unknown(mock_modbus_client):
    """Test setting unknown SG Ready mode returns False."""
    client = QubeClient("1.2.3.4", 502)
    result = await client.set_sg_ready_mode("turbo")
    assert result is False
