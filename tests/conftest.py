"""Shared fixtures for the QubeClient tests.

The ``mock_modbus_connection`` and ``mock_modbus_unit`` fixtures come from the
modbus-connection pytest plugin.
"""

from unittest.mock import MagicMock

import pytest
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent

from python_qube_heatpump import QubeClient


@pytest.fixture
def unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    """The in-memory Modbus unit (unit 1) behind the ``client`` fixture."""
    return mock_modbus_unit


@pytest.fixture
def client(unit: MockModbusUnit) -> QubeClient:
    """A client on a shared unit: the caller owns the connection."""
    return QubeClient("192.0.2.1", unit=unit)


@pytest.fixture
def writes(unit: MockModbusUnit) -> list[WriteEvent]:
    """Every write that reached ``unit``, in order."""
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    return events


@pytest.fixture
def connection_factory(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Make clients that own their connection open an in-memory one, not TCP."""
    factory = MagicMock(return_value=MockModbusConnection())
    monkeypatch.setattr("python_qube_heatpump.client.TmodbusConnection", factory)
    return factory


@pytest.fixture
def owned_connection(connection_factory: MagicMock) -> MockModbusConnection:
    """The connection an owned-mode client opens."""
    return connection_factory.return_value


@pytest.fixture
def owned_client(connection_factory: MagicMock) -> QubeClient:
    """A client that opens and owns its connection."""
    return QubeClient("192.0.2.1")


@pytest.fixture
def owned_unit(
    owned_client: QubeClient, owned_connection: MockModbusConnection
) -> MockModbusUnit:
    """The unit ``owned_client`` talks to."""
    return owned_connection.for_unit(1)
