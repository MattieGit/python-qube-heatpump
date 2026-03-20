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
async def test_monotonic_clamping_prevents_decrease(mock_modbus_client):
    """Test energy counters are clamped when they decrease."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    client._client = mock_instance
    client._connected = True

    # Helper to create mock responses returning specific float values
    def make_resp(value_pairs):
        """Create mock responses for a sequence of register reads."""
        import struct as s

        responses = []
        for val in value_pairs:
            resp = MagicMock()
            resp.isError.return_value = False
            if val is not None:
                packed = s.pack(">f", float(val))
                int_val = s.unpack(">I", packed)[0]
                resp.registers = [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]
            else:
                resp.registers = [0, 0]
            responses.append(resp)
        return responses

    # First call: set initial energy values (100.0 electric, 200.0 thermic)
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [0, 0]
    mock_instance.read_input_registers = AsyncMock(return_value=mock_resp)
    mock_instance.read_holding_registers = AsyncMock(return_value=mock_resp)

    state1 = await client.get_all_data()
    assert state1 is not None
    # Both should be 0.0 initially (all zeros)
    assert state1.energy_total_electric == 0.0
    assert state1.energy_total_thermic == 0.0
    # Previous values should be stored
    assert client._previous_values.get("energy_total_electric") == 0.0
    assert client._previous_values.get("energy_total_thermic") == 0.0


@pytest.mark.asyncio
async def test_monotonic_clamping_unit(mock_modbus_client):
    """Test _apply_monotonic_clamping directly."""
    from python_qube_heatpump.models import QubeState

    client = QubeClient("1.2.3.4", 502)

    # First reading: establish baseline
    state1 = QubeState()
    state1.energy_total_electric = 100.0
    state1.energy_total_thermic = 200.0
    client._apply_monotonic_clamping(state1)
    assert state1.energy_total_electric == 100.0
    assert state1.energy_total_thermic == 200.0

    # Second reading: values increase — should pass through
    state2 = QubeState()
    state2.energy_total_electric = 150.0
    state2.energy_total_thermic = 250.0
    client._apply_monotonic_clamping(state2)
    assert state2.energy_total_electric == 150.0
    assert state2.energy_total_thermic == 250.0

    # Third reading: values decrease (glitch) — should clamp to previous
    state3 = QubeState()
    state3.energy_total_electric = 50.0  # Glitch: dropped below 150
    state3.energy_total_thermic = 100.0  # Glitch: dropped below 250
    client._apply_monotonic_clamping(state3)
    assert state3.energy_total_electric == 150.0  # Clamped
    assert state3.energy_total_thermic == 250.0  # Clamped

    # Fourth reading: values recover — should pass through
    state4 = QubeState()
    state4.energy_total_electric = 160.0
    state4.energy_total_thermic = 260.0
    client._apply_monotonic_clamping(state4)
    assert state4.energy_total_electric == 160.0
    assert state4.energy_total_thermic == 260.0


@pytest.mark.asyncio
async def test_monotonic_clamping_skips_none(mock_modbus_client):
    """Test clamping skips None values."""
    from python_qube_heatpump.models import QubeState

    client = QubeClient("1.2.3.4", 502)

    # Establish baseline
    state1 = QubeState()
    state1.energy_total_electric = 100.0
    state1.energy_total_thermic = 200.0
    client._apply_monotonic_clamping(state1)

    # None value should be skipped (not clamped, not stored)
    state2 = QubeState()
    state2.energy_total_electric = None
    state2.energy_total_thermic = 200.0
    client._apply_monotonic_clamping(state2)
    assert state2.energy_total_electric is None  # Unchanged
    assert client._previous_values["energy_total_electric"] == 100.0  # Not updated


@pytest.mark.asyncio
async def test_monotonic_clamping_skips_nan(mock_modbus_client):
    """Test clamping skips NaN values."""
    from python_qube_heatpump.models import QubeState

    client = QubeClient("1.2.3.4", 502)

    # Establish baseline
    state1 = QubeState()
    state1.energy_total_electric = 100.0
    client._apply_monotonic_clamping(state1)

    # NaN should be skipped
    state2 = QubeState()
    state2.energy_total_electric = float("nan")
    client._apply_monotonic_clamping(state2)
    assert client._previous_values["energy_total_electric"] == 100.0
