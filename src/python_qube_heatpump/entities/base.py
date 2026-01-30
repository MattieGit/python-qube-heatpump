"""Base classes and enums for entity definitions."""

from dataclasses import dataclass
from enum import Enum


class InputType(str, Enum):
    """Modbus input type for reading values."""

    COIL = "coil"
    DISCRETE_INPUT = "discrete_input"
    INPUT_REGISTER = "input"
    HOLDING_REGISTER = "holding"


class DataType(str, Enum):
    """Data type for register values."""

    FLOAT32 = "float32"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"


class Platform(str, Enum):
    """Home Assistant platform type."""

    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SWITCH = "switch"


@dataclass(frozen=True)
class EntityDef:
    """Definition of a Qube heat pump entity.

    This dataclass defines the protocol-level properties of an entity.
    Home Assistant-specific metadata (device_class, state_class, etc.)
    should be added by the integration, not here.
    """

    # Identity
    key: str
    """Unique identifier, e.g., 'temp_supply'."""

    name: str
    """Human-readable name, e.g., 'Supply temperature'."""

    # Modbus specifics
    address: int
    """Register or coil address."""

    input_type: InputType
    """How to read from device (coil, discrete_input, input, holding)."""

    data_type: DataType | None = None
    """Data type for registers. None for coils/discrete inputs."""

    # Platform hint
    platform: Platform = Platform.SENSOR
    """Which HA platform this entity belongs to."""

    # Value transformation
    scale: float | None = None
    """Multiply raw value by this factor."""

    offset: float | None = None
    """Add this to the scaled value."""

    # Unit (protocol-level)
    unit: str | None = None
    """Unit of measurement, e.g., '°C', 'kWh', 'W'."""

    # Write capability
    writable: bool = False
    """Whether this entity can be written to."""
