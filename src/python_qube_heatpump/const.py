"""Constants for Qube Heat Pump."""

from enum import Enum


class ModbusType(str, Enum):
    """Modbus register type."""

    HOLDING = "holding"
    INPUT = "input"


class DataType(str, Enum):
    """Data type."""

    FLOAT32 = "float32"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"


class StatusCode(str, Enum):
    """Heat pump status codes."""

    STANDBY = "standby"
    ALARM = "alarm"
    KEYBOARD_OFF = "keyboard_off"
    COMPRESSOR_STARTUP = "compressor_startup"
    COMPRESSOR_SHUTDOWN = "compressor_shutdown"
    COOLING = "cooling"
    HEATING = "heating"
    START_FAIL = "start_fail"
    HEATING_DHW = "heating_dhw"
    UNKNOWN = "unknown"


# Map numeric status codes to StatusCode enum values
STATUS_CODE_MAP: dict[int, StatusCode] = {
    1: StatusCode.STANDBY,
    2: StatusCode.ALARM,
    6: StatusCode.KEYBOARD_OFF,
    8: StatusCode.COMPRESSOR_STARTUP,
    9: StatusCode.COMPRESSOR_SHUTDOWN,
    14: StatusCode.STANDBY,
    15: StatusCode.COOLING,
    16: StatusCode.HEATING,
    17: StatusCode.START_FAIL,
    18: StatusCode.STANDBY,
    22: StatusCode.HEATING_DHW,
}


def get_status_code(code: int) -> StatusCode:
    """Convert numeric status code to StatusCode enum."""
    return STATUS_CODE_MAP.get(code, StatusCode.UNKNOWN)


# Register definitions (Address, Type, Data Type, Scale, Offset)
# Scale/Offset are None if not used.
# Format: KEY = (Address, ModbusType, DataType, Scale, Offset)

# --- Sensors (Input Registers) ---
PCT_USER_PUMP = (4, ModbusType.INPUT, DataType.FLOAT32, -1, 100)
PCT_SOURCE_PUMP = (6, ModbusType.INPUT, DataType.FLOAT32, -1, 100)
PCT_SOURCE_VALVE = (8, ModbusType.INPUT, DataType.FLOAT32, None, None)
REQ_DHW = (14, ModbusType.INPUT, DataType.FLOAT32, None, None)
REQ_COMPRESSOR = (16, ModbusType.INPUT, DataType.FLOAT32, None, None)
FLOW_RATE = (18, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_SUPPLY = (20, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_RETURN = (22, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_SOURCE_IN = (24, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_SOURCE_OUT = (26, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_ROOM = (28, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_DHW = (30, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_OUTSIDE = (32, ModbusType.INPUT, DataType.FLOAT32, None, None)
COP_CALC = (34, ModbusType.INPUT, DataType.FLOAT32, None, None)
POWER_THERMIC = (36, ModbusType.INPUT, DataType.FLOAT32, None, None)
STATUS_CODE = (38, ModbusType.INPUT, DataType.UINT16, None, None)
TEMP_REG_SETPOINT = (39, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_COOL_SETPOINT = (41, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_HEAT_SETPOINT = (43, ModbusType.INPUT, DataType.FLOAT32, None, None)
COMPRESSOR_SPEED = (45, ModbusType.INPUT, DataType.FLOAT32, 60, None)  # RPM
TEMP_DHW_SETPOINT = (47, ModbusType.INPUT, DataType.FLOAT32, None, None)
HOURS_DHW = (50, ModbusType.INPUT, DataType.INT16, None, None)
HOURS_HEAT = (52, ModbusType.INPUT, DataType.INT16, None, None)
HOURS_COOL = (54, ModbusType.INPUT, DataType.INT16, None, None)
HOURS_HEATER_1 = (56, ModbusType.INPUT, DataType.INT16, None, None)
HOURS_HEATER_2 = (58, ModbusType.INPUT, DataType.INT16, None, None)
HOURS_HEATER_3 = (60, ModbusType.INPUT, DataType.INT16, None, None)
POWER_ELECTRIC_CALC = (61, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_PLANT_SETPOINT = (65, ModbusType.INPUT, DataType.FLOAT32, None, None)
ENERGY_ELECTRIC_TOTAL = (69, ModbusType.INPUT, DataType.FLOAT32, None, None)
ENERGY_THERMIC_TOTAL = (71, ModbusType.INPUT, DataType.FLOAT32, None, None)
TEMP_ROOM_MODBUS = (75, ModbusType.INPUT, DataType.FLOAT32, None, None)

# --- Configuration (Holding Registers) ---
SETPOINT_HEAT_DAY = (27, ModbusType.HOLDING, DataType.FLOAT32, None, None)
SETPOINT_HEAT_NIGHT = (29, ModbusType.HOLDING, DataType.FLOAT32, None, None)
SETPOINT_COOL_DAY = (31, ModbusType.HOLDING, DataType.FLOAT32, None, None)
SETPOINT_COOL_NIGHT = (33, ModbusType.HOLDING, DataType.FLOAT32, None, None)
DT_DHW = (43, ModbusType.HOLDING, DataType.INT16, None, None)
MIN_TEMP_DHW = (44, ModbusType.HOLDING, DataType.FLOAT32, None, None)
TEMP_DHW_PROG = (46, ModbusType.HOLDING, DataType.FLOAT32, None, None)
MIN_SETPOINT_BUFFER = (99, ModbusType.HOLDING, DataType.FLOAT32, None, None)
USER_HEAT_SETPOINT = (101, ModbusType.HOLDING, DataType.FLOAT32, None, None)
USER_COOL_SETPOINT = (103, ModbusType.HOLDING, DataType.FLOAT32, None, None)
MAX_SETPOINT_BUFFER = (169, ModbusType.HOLDING, DataType.FLOAT32, None, None)
USER_DHW_SETPOINT = (173, ModbusType.HOLDING, DataType.FLOAT32, None, None)
