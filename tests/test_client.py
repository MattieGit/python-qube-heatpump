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
async def test_read_registers(mock_modbus_client):
    """Test reading registers."""
    client = QubeClient("1.2.3.4", 502)
    mock_instance = mock_modbus_client.return_value
    mock_instance.connected = True
    # Mock response
    mock_resp = MagicMock()
    mock_resp.isError.return_value = False
    mock_resp.registers = [123]
    # Setup the read_holding_registers method on the mock
    mock_instance.read_holding_registers = AsyncMock(return_value=mock_resp)
    # We need to manually set the client on the wrapper if we bypass connect
    client._client = mock_instance
    result = await client.read_registers(10, 1)
    assert result == [123]
    mock_instance.read_holding_registers.assert_called_once()


@pytest.mark.asyncio
async def test_decode_registers():
    """Test Register Decoding."""
    # float32: 24.5 = 0x41C40000 -> 16836, 0 (Big Endian)
    # struct.unpack('>f', struct.pack('>HH', 16836, 0)) -> 24.5
    regs = [16836, 0]
    val = QubeClient.decode_registers(regs, "float32")
    assert round(val, 1) == 24.5
    # int16 (negative): -10 = 0xFFF6 = 65526
    regs = [65526]
    val = QubeClient.decode_registers(regs, "int16")
    assert val == -10
