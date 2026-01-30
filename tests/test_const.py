"""Tests for constants."""

from python_qube_heatpump.const import (
    StatusCode,
    STATUS_CODE_MAP,
    get_status_code,
)


def test_status_code_enum():
    """Test StatusCode enum values."""
    assert StatusCode.STANDBY.value == "standby"
    assert StatusCode.ALARM.value == "alarm"
    assert StatusCode.HEATING.value == "heating"
    assert StatusCode.COOLING.value == "cooling"
    assert StatusCode.HEATING_DHW.value == "heating_dhw"
    assert StatusCode.UNKNOWN.value == "unknown"


def test_status_code_map_standby():
    """Test standby status codes (1, 14, 18)."""
    assert STATUS_CODE_MAP[1] == StatusCode.STANDBY
    assert STATUS_CODE_MAP[14] == StatusCode.STANDBY
    assert STATUS_CODE_MAP[18] == StatusCode.STANDBY


def test_status_code_map_operations():
    """Test operational status codes."""
    assert STATUS_CODE_MAP[15] == StatusCode.COOLING
    assert STATUS_CODE_MAP[16] == StatusCode.HEATING
    assert STATUS_CODE_MAP[22] == StatusCode.HEATING_DHW


def test_status_code_map_alarms():
    """Test alarm and error status codes."""
    assert STATUS_CODE_MAP[2] == StatusCode.ALARM
    assert STATUS_CODE_MAP[17] == StatusCode.START_FAIL


def test_status_code_map_transitions():
    """Test transition status codes."""
    assert STATUS_CODE_MAP[8] == StatusCode.COMPRESSOR_STARTUP
    assert STATUS_CODE_MAP[9] == StatusCode.COMPRESSOR_SHUTDOWN


def test_get_status_code_known():
    """Test get_status_code with known codes."""
    assert get_status_code(1) == StatusCode.STANDBY
    assert get_status_code(16) == StatusCode.HEATING
    assert get_status_code(22) == StatusCode.HEATING_DHW


def test_get_status_code_unknown():
    """Test get_status_code with unknown codes."""
    assert get_status_code(0) == StatusCode.UNKNOWN
    assert get_status_code(99) == StatusCode.UNKNOWN
    assert get_status_code(-1) == StatusCode.UNKNOWN
