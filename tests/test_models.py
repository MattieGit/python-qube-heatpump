"""Tests for models."""

from python_qube_heatpump.models import QubeState


def test_qube_state_creation():
    """Test QubeState dataclass creation."""
    state = QubeState()
    assert state.temp_supply is None
    assert state.status_code is None
    assert state._extended == {}


def test_qube_state_with_values():
    """Test QubeState with values."""
    state = QubeState(
        temp_supply=35.5,
        temp_return=30.2,
        status_code=1,
    )
    assert state.temp_supply == 35.5
    assert state.temp_return == 30.2
    assert state.status_code == 1


def test_qube_state_extended_dict():
    """Test QubeState _extended dict functionality."""
    state = QubeState()
    state.set_extended("custom_sensor", 42.0)
    assert state._extended["custom_sensor"] == 42.0


def test_qube_state_get_typed_field():
    """Test get() returns typed field value."""
    state = QubeState(temp_supply=35.5)
    assert state.get("temp_supply") == 35.5


def test_qube_state_get_typed_field_none_returns_default():
    """Test get() returns default when typed field is None."""
    state = QubeState()
    assert state.get("temp_supply") is None
    assert state.get("temp_supply", 0.0) == 0.0


def test_qube_state_get_extended_value():
    """Test get() returns extended dict value."""
    state = QubeState()
    state.set_extended("custom_sensor", 42.0)
    assert state.get("custom_sensor") == 42.0


def test_qube_state_get_unknown_key_returns_default():
    """Test get() returns default for unknown key."""
    state = QubeState()
    assert state.get("unknown_key") is None
    assert state.get("unknown_key", "default") == "default"


def test_qube_state_typed_fields_take_precedence():
    """Test that typed fields take precedence over _extended."""
    state = QubeState(temp_supply=35.5)
    state.set_extended("temp_supply", 99.9)  # Should not override typed field
    assert state.get("temp_supply") == 35.5
