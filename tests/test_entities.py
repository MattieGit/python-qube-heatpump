"""Tests for entity definitions."""

import pytest

from python_qube_heatpump.entities.base import (
    DataType,
    EntityDef,
    InputType,
    Platform,
)


def test_input_type_enum():
    """Test InputType enum values."""
    assert InputType.COIL.value == "coil"
    assert InputType.DISCRETE_INPUT.value == "discrete_input"
    assert InputType.INPUT_REGISTER.value == "input"
    assert InputType.HOLDING_REGISTER.value == "holding"


def test_data_type_enum():
    """Test DataType enum values."""
    assert DataType.FLOAT32.value == "float32"
    assert DataType.INT16.value == "int16"
    assert DataType.UINT16.value == "uint16"


def test_platform_enum():
    """Test Platform enum values."""
    assert Platform.SENSOR.value == "sensor"
    assert Platform.BINARY_SENSOR.value == "binary_sensor"
    assert Platform.SWITCH.value == "switch"


def test_entity_def_creation():
    """Test EntityDef dataclass creation."""
    entity = EntityDef(
        key="temp_supply",
        name="Supply temperature",
        address=20,
        input_type=InputType.INPUT_REGISTER,
        data_type=DataType.FLOAT32,
        platform=Platform.SENSOR,
        unit="°C",
    )
    assert entity.key == "temp_supply"
    assert entity.name == "Supply temperature"
    assert entity.address == 20
    assert entity.input_type == InputType.INPUT_REGISTER
    assert entity.data_type == DataType.FLOAT32
    assert entity.platform == Platform.SENSOR
    assert entity.unit == "°C"
    assert entity.scale is None
    assert entity.offset is None
    assert entity.writable is False


def test_entity_def_is_frozen():
    """Test EntityDef is immutable."""
    entity = EntityDef(
        key="test",
        name="Test",
        address=0,
        input_type=InputType.COIL,
        platform=Platform.BINARY_SENSOR,
    )
    with pytest.raises(AttributeError):
        entity.key = "changed"
