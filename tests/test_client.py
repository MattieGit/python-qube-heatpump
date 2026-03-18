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
