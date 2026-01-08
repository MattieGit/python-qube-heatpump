"""Client for Qube Heat Pump."""

import logging
import struct
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient

from . import const
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

    async def close(self) -> None:
        """Close connection."""
        self._client.close()
        self._connected = False

    async def get_all_data(self) -> QubeState:
        """Fetch all definition data and return a state object."""
        # Note: In a real implementation you might want to optimize this
        # by reading contiguous blocks instead of one-by-one.
        # For now, we wrap the individual reads for abstraction.

        state = QubeState()

        # Helper to read and assign
        async def _read(const_def):
            return await self.read_value(const_def)

        # Fetch basic sensors
        state.temp_supply = await _read(const.TEMP_SUPPLY)
        state.temp_return = await _read(const.TEMP_RETURN)
        state.temp_outside = await _read(const.TEMP_OUTSIDE)
        state.temp_dhw = await _read(const.TEMP_DHW)

        return state

    async def read_value(self, definition: tuple) -> Optional[float]:
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
                    address, count, slave=self.unit
                )
            else:
                result = await self._client.read_holding_registers(
                    address, count, slave=self.unit
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
