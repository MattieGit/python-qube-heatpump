"""Python library for Qube Heat Pump Modbus communication."""

from .client import QubeClient
from .const import (
    DataType,
    ModbusType,
    StatusCode,
    STATUS_CODE_MAP,
    get_status_code,
    resolve_status,
)
from .entities import (
    BINARY_SENSORS,
    EntityDef,
    InputType,
    Platform,
    SENSORS,
    SWITCHES,
)
from .mdns import QubeDeviceInfo, async_get_device_info, parse_device_info
from .models import QubeState
from .network import async_get_mac_address

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
    "resolve_status",
    # Network
    "async_get_mac_address",
    # mDNS device information
    "QubeDeviceInfo",
    "async_get_device_info",
    "parse_device_info",
]
