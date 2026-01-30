"""Client for Qube Heat Pump."""

from __future__ import annotations

import logging
import struct
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from . import const
from .entities import BINARY_SENSORS, SENSORS, SWITCHES, EntityDef
from .entities.base import DataType, InputType
from .models import QubeState

_LOGGER = logging.getLogger(__name__)


class QubeClient:
    """Qube Modbus Client."""

    def __init__(self, host: str, port: int = 502, unit_id: int = 1):
        """Initialize."""
        self.host = host
        self.port = port
        self.unit = unit_id
        self._client = AsyncModbusTcpClient(host, port=port)
        self._connected = False

    async def connect(self) -> bool:
        """Connect to the Modbus server."""
        if not self._connected:
            self._connected = await self._client.connect()
        return self._connected

    @property
    def is_connected(self) -> bool:
        """Return True if connected."""
        return self._connected

    async def close(self) -> None:
        """Close connection."""
        self._client.close()
        self._connected = False

    async def get_all_data(self) -> QubeState:
        """Fetch all definition data and return a state object.

        This fetches core sensors for the official HA integration.
        """
        state = QubeState()

        # Helper to read and assign
        async def _read(const_def):
            return await self.read_value(const_def)

        # Fetch temperature sensors
        state.temp_supply = await _read(const.TEMP_SUPPLY)
        state.temp_return = await _read(const.TEMP_RETURN)
        state.temp_source_in = await _read(const.TEMP_SOURCE_IN)
        state.temp_source_out = await _read(const.TEMP_SOURCE_OUT)
        state.temp_room = await _read(const.TEMP_ROOM)
        state.temp_dhw = await _read(const.TEMP_DHW)
        state.temp_outside = await _read(const.TEMP_OUTSIDE)

        # Fetch power and energy sensors
        state.power_thermic = await _read(const.POWER_THERMIC)
        state.power_electric = await _read(const.POWER_ELECTRIC_CALC)
        state.energy_total_electric = await _read(const.ENERGY_ELECTRIC_TOTAL)
        state.energy_total_thermic = await _read(const.ENERGY_THERMIC_TOTAL)
        state.cop_calc = await _read(const.COP_CALC)

        # Fetch operation sensors
        state.status_code = await _read(const.STATUS_CODE)
        state.compressor_speed = await _read(const.COMPRESSOR_SPEED)
        state.flow_rate = await _read(const.FLOW_RATE)

        # Fetch setpoints (holding registers)
        state.setpoint_room_heat_day = await _read(const.SETPOINT_HEAT_DAY)
        state.setpoint_room_heat_night = await _read(const.SETPOINT_HEAT_NIGHT)
        state.setpoint_room_cool_day = await _read(const.SETPOINT_COOL_DAY)
        state.setpoint_room_cool_night = await _read(const.SETPOINT_COOL_NIGHT)
        state.setpoint_dhw = await _read(const.USER_DHW_SETPOINT)

        return state

    async def get_all_entities(self) -> dict[str, Any]:
        """Fetch all entity values from library definitions.

        This reads all sensors, binary sensors, and switches defined in the
        library's entity definitions. Used by the HACS integration.

        Returns:
            Dictionary mapping entity keys to their values.
        """
        results: dict[str, Any] = {}

        # Read all sensors
        for key, entity in SENSORS.items():
            try:
                results[key] = await self.read_entity(entity)
            except Exception as exc:
                _LOGGER.debug("Error reading sensor %s: %s", key, exc)
                results[key] = None

        # Read all binary sensors
        for key, entity in BINARY_SENSORS.items():
            try:
                results[key] = await self.read_entity(entity)
            except Exception as exc:
                _LOGGER.debug("Error reading binary sensor %s: %s", key, exc)
                results[key] = None

        # Read all switches
        for key, entity in SWITCHES.items():
            try:
                results[key] = await self.read_entity(entity)
            except Exception as exc:
                _LOGGER.debug("Error reading switch %s: %s", key, exc)
                results[key] = None

        return results

    async def read_value(self, definition: tuple) -> float | None:
        """Read a single value based on the constant definition."""
        address, reg_type, data_type, scale, offset = definition

        count = (
            2
            if data_type
            in (const.DataType.FLOAT32, const.DataType.UINT32, const.DataType.INT32)
            else 1
        )

        try:
            if reg_type == const.ModbusType.INPUT:
                result = await self._client.read_input_registers(
                    address, count=count, device_id=self.unit
                )
            else:
                result = await self._client.read_holding_registers(
                    address, count=count, device_id=self.unit
                )

            if result.isError():
                _LOGGER.warning("Error reading address %s", address)
                return None

            regs = result.registers
            val = 0

            # Manual decoding to avoid pymodbus.payload dependencies
            # Assuming Little Endian Word Order for 32-bit values [LSW, MSW] per standard Modbus often used
            # But the original code used Endian.Little WordOrder.
            # Decoder: byteorder=Endian.Big, wordorder=Endian.Little
            # Big Endian Bytes: [H, L]
            # Little Endian Words: [Reg0, Reg1] -> [LSW, MSW]
            #
            # Example Float32: 123.456
            # Reg0 (LSW)
            # Reg1 (MSW)
            # Full 32-bit int: (Reg1 << 16) | Reg0
            # Then pack as >I (Big Endian 32-bit int) and unpack as >f (Big Endian float)?
            #
            # Wait, PyModbus BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Little)
            # ByteOrder Big: Normal network byte order per register.
            # WordOrder Little: The first register is the least significant word.
            #
            # So:
            # 32-bit value = (regs[1] << 16) | regs[0]
            # Then interpret that 32-bit integer as a float.
            # To interpret int bits as float in Python: struct.unpack('!f', struct.pack('!I', int_val))[0]

            if data_type == const.DataType.FLOAT32:
                # Combine 2 registers, Little Endian Word Order
                int_val = (regs[1] << 16) | regs[0]
                val = struct.unpack(">f", struct.pack(">I", int_val))[0]
            elif data_type == const.DataType.INT16:
                val = regs[0]
                # Signed 16-bit
                if val > 32767:
                    val -= 65536
            elif data_type == const.DataType.UINT16:
                val = regs[0]
            elif data_type == const.DataType.UINT32:
                val = (regs[1] << 16) | regs[0]
            elif data_type == const.DataType.INT32:
                val = (regs[1] << 16) | regs[0]
                if val > 2147483647:
                    val -= 4294967296
            else:
                val = 0

            if scale is not None:
                val *= scale
            if offset is not None:
                val += offset

            return val

        except Exception as e:
            _LOGGER.error("Exception reading address %s: %s", address, e)
            return None

    async def read_entity(self, entity: EntityDef) -> Any:
        """Read a single entity value based on EntityDef.

        Args:
            entity: The entity definition to read.

        Returns:
            The read value (float, int, or bool depending on entity type).
        """
        # Determine register count based on data type
        # Use string comparison to handle potential enum class differences
        data_type_str = entity.data_type.value if entity.data_type else None
        if data_type_str in ("float32", "uint32", "int32"):
            count = 2
        else:
            count = 1

        _LOGGER.debug(
            "read_entity: key=%s addr=%s input_type=%s data_type=%s count=%s",
            entity.key, entity.address, entity.input_type, data_type_str, count
        )

        try:
            # Read based on input type (use string comparison for safety)
            input_type_str = entity.input_type.value if entity.input_type else None

            if input_type_str == "coil":
                result = await self._client.read_coils(
                    entity.address, count=1, device_id=self.unit
                )
                if result.isError():
                    _LOGGER.warning("Error reading coil %s", entity.address)
                    return None
                return bool(result.bits[0])

            if input_type_str == "discrete_input":
                result = await self._client.read_discrete_inputs(
                    entity.address, count=1, device_id=self.unit
                )
                if result.isError():
                    _LOGGER.warning("Error reading discrete input %s", entity.address)
                    return None
                return bool(result.bits[0])

            if input_type_str == "input":
                result = await self._client.read_input_registers(
                    entity.address, count=count, device_id=self.unit
                )
            else:  # holding
                result = await self._client.read_holding_registers(
                    entity.address, count=count, device_id=self.unit
                )

            if result.isError():
                _LOGGER.warning("Error reading address %s", entity.address)
                return None

            regs = result.registers
            val: float | int = 0

            _LOGGER.debug(
                "read_entity: key=%s raw_regs=%s", entity.key, regs
            )

            # Decode based on data type (use string comparison for safety)
            if data_type_str == "float32":
                int_val = (regs[1] << 16) | regs[0]
                val = struct.unpack(">f", struct.pack(">I", int_val))[0]
                _LOGGER.debug(
                    "read_entity: key=%s float32 int_val=%s decoded=%s",
                    entity.key, int_val, val
                )
            elif data_type_str == "int16":
                val = regs[0]
                if val > 32767:
                    val -= 65536
            elif data_type_str == "uint16":
                val = regs[0]
            elif data_type_str == "uint32":
                val = (regs[1] << 16) | regs[0]
            elif data_type_str == "int32":
                val = (regs[1] << 16) | regs[0]
                if val > 2147483647:
                    val -= 4294967296

            # Apply scale and offset
            if entity.scale is not None:
                val = val * entity.scale
            if entity.offset is not None:
                val = val + entity.offset

            _LOGGER.debug(
                "read_entity: key=%s final_value=%s (scale=%s, offset=%s)",
                entity.key, val, entity.scale, entity.offset
            )

            return val

        except Exception as e:
            _LOGGER.error("Exception reading entity %s: %s", entity.key, e)
            return None

    async def read_sensor(self, key: str) -> float | int | None:
        """Read a sensor value by key.

        Args:
            key: The sensor key (e.g., 'temp_supply').

        Returns:
            The sensor value, or None if not found or error.
        """
        entity = SENSORS.get(key)
        if entity is None:
            _LOGGER.warning("Unknown sensor key: %s", key)
            return None
        return await self.read_entity(entity)

    async def read_binary_sensor(self, key: str) -> bool | None:
        """Read a binary sensor value by key.

        Args:
            key: The binary sensor key (e.g., 'dout_srcpmp_val').

        Returns:
            The binary sensor value, or None if not found or error.
        """
        entity = BINARY_SENSORS.get(key)
        if entity is None:
            _LOGGER.warning("Unknown binary sensor key: %s", key)
            return None
        return await self.read_entity(entity)

    async def read_switch(self, key: str) -> bool | None:
        """Read a switch state by key.

        Args:
            key: The switch key (e.g., 'bms_summerwinter').

        Returns:
            The switch state, or None if not found or error.
        """
        entity = SWITCHES.get(key)
        if entity is None:
            _LOGGER.warning("Unknown switch key: %s", key)
            return None
        return await self.read_entity(entity)

    async def read_all_sensors(self) -> dict[str, Any]:
        """Read all sensor values.

        Returns:
            Dictionary mapping sensor keys to their values.
        """
        result: dict[str, Any] = {}
        for key, entity in SENSORS.items():
            result[key] = await self.read_entity(entity)
        return result

    async def read_all_binary_sensors(self) -> dict[str, bool | None]:
        """Read all binary sensor values.

        Returns:
            Dictionary mapping binary sensor keys to their values.
        """
        result: dict[str, bool | None] = {}
        for key, entity in BINARY_SENSORS.items():
            result[key] = await self.read_entity(entity)
        return result

    async def read_all_switches(self) -> dict[str, bool | None]:
        """Read all switch states.

        Returns:
            Dictionary mapping switch keys to their states.
        """
        result: dict[str, bool | None] = {}
        for key, entity in SWITCHES.items():
            result[key] = await self.read_entity(entity)
        return result

    async def write_switch(self, key: str, value: bool) -> bool:
        """Write a switch state by key.

        Args:
            key: The switch key (e.g., 'bms_summerwinter').
            value: True to turn on, False to turn off.

        Returns:
            True if write succeeded, False otherwise.
        """
        entity = SWITCHES.get(key)
        if entity is None:
            _LOGGER.warning("Unknown switch key: %s", key)
            return False

        if not entity.writable:
            _LOGGER.warning("Switch %s is not writable", key)
            return False

        try:
            result = await self._client.write_coil(
                entity.address, value, device_id=self.unit
            )
            if result.isError():
                _LOGGER.warning("Error writing switch %s", key)
                return False
            return True
        except Exception as e:
            _LOGGER.error("Exception writing switch %s: %s", key, e)
            return False

    async def write_setpoint(self, key: str, value: float) -> bool:
        """Write a setpoint value by key.

        Args:
            key: The sensor key for the setpoint (e.g., 'setpoint_dhw').
            value: The value to write.

        Returns:
            True if write succeeded, False otherwise.
        """
        entity = SENSORS.get(key)
        if entity is None:
            _LOGGER.warning("Unknown sensor key: %s", key)
            return False

        if not entity.writable:
            _LOGGER.warning("Sensor %s is not writable", key)
            return False

        if entity.input_type != InputType.HOLDING_REGISTER:
            _LOGGER.warning("Sensor %s is not a holding register", key)
            return False

        try:
            # Reverse scale/offset if needed
            write_value = value
            if entity.offset is not None:
                write_value = write_value - entity.offset
            if entity.scale is not None:
                write_value = write_value / entity.scale

            # Encode based on data type
            if entity.data_type == DataType.FLOAT32:
                # Pack as big-endian float, then split into two registers
                packed = struct.pack(">f", write_value)
                int_val = struct.unpack(">I", packed)[0]
                regs = [int_val & 0xFFFF, (int_val >> 16) & 0xFFFF]
                result = await self._client.write_registers(
                    entity.address, regs, device_id=self.unit
                )
            elif entity.data_type == DataType.INT16:
                if write_value < 0:
                    write_value = int(write_value) + 65536
                result = await self._client.write_register(
                    entity.address, int(write_value), device_id=self.unit
                )
            elif entity.data_type == DataType.UINT16:
                result = await self._client.write_register(
                    entity.address, int(write_value), device_id=self.unit
                )
            else:
                _LOGGER.warning("Unsupported data type for writing: %s", entity.data_type)
                return False

            if result.isError():
                _LOGGER.warning("Error writing setpoint %s", key)
                return False
            return True

        except Exception as e:
            _LOGGER.error("Exception writing setpoint %s: %s", key, e)
            return False
