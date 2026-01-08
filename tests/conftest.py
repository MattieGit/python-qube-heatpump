import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_modbus_client(mocker):
    """Mock the Modbus client."""
    mock_client = mocker.patch("python_qube_heatpump.client.AsyncModbusTcpClient")
    mock_instance = mock_client.return_value
    mock_instance.connect = AsyncMock(return_value=True)
    mock_instance.close = AsyncMock()
    mock_instance.read_holding_registers = AsyncMock()
    mock_instance.read_input_registers = AsyncMock()
    mock_instance.write_register = AsyncMock()
    mock_instance.write_registers = AsyncMock()
    return mock_client
