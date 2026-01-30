"""Python library for Qube Heat Pump Modbus communication."""

from .client import QubeClient
from .const import (
    DataType,
    ModbusType,
    StatusCode,
    STATUS_CODE_MAP,
    get_status_code,
)
from .entities import (
    BINARY_SENSORS,
    EntityDef,
    InputType,
    Platform,
    SENSORS,
    SWITCHES,
)
from .models import QubeState

__all__ = [
    # Client
    "QubeClient",
    # State
    "QubeState",
    # Entity definitions
    "BINARY_SENSORS",
    "EntityDef",
    "InputType",
    "Platform",
    "SENSORS",
    "SWITCHES",
    # Constants
    "DataType",
    "ModbusType",
    "StatusCode",
    "STATUS_CODE_MAP",
    "get_status_code",
]
