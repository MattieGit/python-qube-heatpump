"""Tests for entity definitions."""

import pytest

from python_qube_heatpump.entities import (
    BINARY_SENSORS,
    DataType,
    EntityDef,
    InputType,
    Platform,
    SENSORS,
    SWITCHES,
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


def test_binary_sensor_definitions_exist():
    """Test binary sensor definitions are available."""
    from python_qube_heatpump.entities.binary_sensors import BINARY_SENSORS

    # Check we have binary sensors
    assert len(BINARY_SENSORS) > 0

    # Check a specific one
    assert "dout_srcpmp_val" in BINARY_SENSORS
    entity = BINARY_SENSORS["dout_srcpmp_val"]
    assert entity.platform == Platform.BINARY_SENSOR
    assert entity.input_type == InputType.DISCRETE_INPUT
    assert entity.address == 0


def test_all_binary_sensors_have_required_fields():
    """Test all binary sensors have required fields."""
    from python_qube_heatpump.entities.binary_sensors import BINARY_SENSORS

    for key, entity in BINARY_SENSORS.items():
        assert entity.key == key, f"Key mismatch for {key}"
        assert entity.name, f"Missing name for {key}"
        assert entity.platform == Platform.BINARY_SENSOR, f"Wrong platform for {key}"
        assert entity.input_type in (
            InputType.DISCRETE_INPUT,
            InputType.COIL,
            InputType.HOLDING_REGISTER,
            InputType.INPUT_REGISTER,
        ), f"Invalid input_type for {key}"


def test_sensor_definitions_exist():
    """Test sensor definitions are available."""
    from python_qube_heatpump.entities.sensors import SENSORS

    assert len(SENSORS) > 0

    # Check core sensors exist
    assert "temp_supply" in SENSORS
    assert "temp_return" in SENSORS
    assert "power_thermic" in SENSORS

    # Verify a sensor's properties
    temp = SENSORS["temp_supply"]
    assert temp.platform == Platform.SENSOR
    assert temp.input_type == InputType.INPUT_REGISTER
    assert temp.data_type == DataType.FLOAT32
    assert temp.unit == "°C"


def test_all_sensors_have_required_fields():
    """Test all sensors have required fields."""
    from python_qube_heatpump.entities.sensors import SENSORS

    for key, entity in SENSORS.items():
        assert entity.key == key, f"Key mismatch for {key}"
        assert entity.name, f"Missing name for {key}"
        assert entity.platform == Platform.SENSOR, f"Wrong platform for {key}"
        assert entity.data_type is not None, f"Missing data_type for {key}"


def test_switch_definitions_exist():
    """Test switch definitions are available."""
    from python_qube_heatpump.entities.switches import SWITCHES

    assert len(SWITCHES) > 0

    # Check core switches exist
    assert "bms_summerwinter" in SWITCHES
    assert "modbus_demand" in SWITCHES
    assert "bms_sgready_a" in SWITCHES

    # Verify a switch's properties
    switch = SWITCHES["bms_summerwinter"]
    assert switch.platform == Platform.SWITCH
    assert switch.input_type == InputType.COIL
    assert switch.writable is True


def test_all_switches_have_required_fields():
    """Test all switches have required fields."""
    from python_qube_heatpump.entities.switches import SWITCHES

    for key, entity in SWITCHES.items():
        assert entity.key == key, f"Key mismatch for {key}"
        assert entity.name, f"Missing name for {key}"
        assert entity.platform == Platform.SWITCH, f"Wrong platform for {key}"
        assert entity.input_type == InputType.COIL, f"Wrong input_type for {key}"
        assert entity.writable is True, f"Switch {key} should be writable"


def test_package_exports():
    """Test that all entity collections are exported from package."""
    # Test that we can import from the package level
    assert len(BINARY_SENSORS) > 0
    assert len(SENSORS) > 0
    assert len(SWITCHES) > 0

    # Verify types are correct
    for entity in BINARY_SENSORS.values():
        assert isinstance(entity, EntityDef)
    for entity in SENSORS.values():
        assert isinstance(entity, EntityDef)
    for entity in SWITCHES.values():
        assert isinstance(entity, EntityDef)
