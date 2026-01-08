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
    # 24.5 = 0x41C40000 -> 16836 (0x41C4), 0 (0x0000) (Big Endian)
    # Our decoder expects [0, 16836] for Little Endian Word Order?
    # Logic in client.py: int_val = (regs[1] << 16) | regs[0]
    # To get 0x41C40000: regs[1]=0x41C4, regs[0]=0x0000
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [0, 16836]

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
