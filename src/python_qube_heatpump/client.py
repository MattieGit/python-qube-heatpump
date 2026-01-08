"""Client for Qube Heat Pump."""

import logging
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

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

            decoder = BinaryPayloadDecoder.fromRegisters(
                result.registers, byteorder=Endian.Big, wordorder=Endian.Little
            )

            if data_type == const.DataType.FLOAT32:
                val = decoder.decode_32bit_float()
            elif data_type == const.DataType.INT16:
                val = decoder.decode_16bit_int()
            elif data_type == const.DataType.UINT16:
                val = decoder.decode_16bit_uint()
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
