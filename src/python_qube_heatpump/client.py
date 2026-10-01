"""Client for Qube Heat Pump."""

from __future__ import annotations

import contextlib
import logging
import math
import struct
import time
from collections.abc import Iterable
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from . import const
from .entities import BINARY_SENSORS, SENSORS, SWITCHES, EntityDef
from .entities.base import DataType, InputType
from .models import QubeState

_LOGGER = logging.getLogger(__name__)

# Exceptions meaning the TCP link (or the device behind it) stopped answering,
# as opposed to a Modbus error reply to one request. pymodbus raises
# ConnectionException when it cannot connect and ModbusIOException when a
# request got no response after its retries. OSError covers socket errors
# and TimeoutError.
_LINK_ERRORS: tuple[type[Exception], ...] = (
    ConnectionException,
    ModbusIOException,
    OSError,
)


class _BlockReadError(Exception):
    """A block read got a Modbus error reply or a short response."""


# Entities read by get_all_data() (used by the official HA core integration).
# These mirror the register definitions in `const` exactly (address, scale,
# offset) so batching cannot change any value get_all_data() returns.
# Note: some of these intentionally differ from the corresponding entries in
# entities/sensors.py (e.g. compressor_speed has a x60 RPM scale here but not
# there; cop_calc is unrounded here but rounded to 1 decimal there) — reusing
# SENSORS would silently change get_all_data()'s output, so a dedicated table
# is kept instead.
# Format: (key, address, input_type, data_type, scale, offset)
_CORE_STATE_REGISTERS: tuple[
    tuple[str, int, InputType, DataType, float | None, float | None], ...
] = (
    ("temp_supply", 20, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_return", 22, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_source_in", 24, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_source_out", 26, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_room", 28, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_dhw", 30, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("temp_outside", 32, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("power_thermic", 36, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("power_electric", 61, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    (
        "energy_total_electric",
        69,
        InputType.INPUT_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    (
        "energy_total_thermic",
        71,
        InputType.INPUT_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    ("cop_calc", 34, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    ("status_code", 38, InputType.INPUT_REGISTER, DataType.UINT16, None, None),
    ("compressor_speed", 45, InputType.INPUT_REGISTER, DataType.FLOAT32, 60, None),
    ("flow_rate", 18, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
    (
        "setpoint_room_heat_day",
        27,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    (
        "setpoint_room_heat_night",
        29,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    (
        "setpoint_room_cool_day",
        31,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    (
        "setpoint_room_cool_night",
        33,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    ("setpoint_dhw", 173, InputType.HOLDING_REGISTER, DataType.FLOAT32, None, None),
    (
        "usr_pid_heatsetp",
        101,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    (
        "usr_pid_coolsetp",
        103,
        InputType.HOLDING_REGISTER,
        DataType.FLOAT32,
        None,
        None,
    ),
    ("modbus_roomtemp", 75, InputType.INPUT_REGISTER, DataType.FLOAT32, None, None),
)

_CORE_STATE_ENTITIES: tuple[EntityDef, ...] = tuple(
    EntityDef(
        key=key,
        name=key,
        address=address,
        input_type=input_type,
        data_type=data_type,
        scale=scale,
        offset=offset,
    )
    for key, address, input_type, data_type, scale, offset in _CORE_STATE_REGISTERS
)


class QubeClient:
    """Qube Modbus Client."""

    # Block-read planning limits. Small address gaps within a block are
    # read along and discarded; a failed block falls back to individual
    # entity reads, so gap registers can never break a value.
    _MAX_BLOCK_REGISTERS = 100  # Modbus allows at most 125 per request
    _MAX_BLOCK_BITS = 256
    _MAX_GAP_REGISTERS = 8
    _MAX_GAP_BITS = 16

    def __init__(self, host: str, port: int = 502, unit_id: int = 1):
        """Initialize."""
        self.host = host
        self.port = port
        self.unit = unit_id
        self._client = AsyncModbusTcpClient(host, port=port)
        self._connected = False
        # Backoff state
        self._backoff_seconds: float = 0.0
        self._backoff_max: float = 60.0
        self._next_connect_at: float = 0.0
        # Monotonic clamping for total_increasing counters
        self._monotonic_cache: dict[str, float] = {}
        # Per-key count of consecutive reads that fell below the cached
        # maximum by more than the reset threshold (see clamp_monotonic)
        self._monotonic_reset_pending: dict[str, int] = {}
        # Reads that already produced a WARNING (transient failures are
        # logged once per target, then at DEBUG to avoid log spam)
        self._read_failures_warned: set[str] = set()

    def _log_read_failure(self, target: str, exc: Exception) -> None:
        """Log a read failure: WARNING on first occurrence per target, DEBUG after.

        Transient Modbus timeouts recover on the next poll cycle, so
        repeated occurrences should not flood the log at high severity.
        """
        if target in self._read_failures_warned:
            _LOGGER.debug("Exception reading %s: %s", target, exc)
        else:
            self._read_failures_warned.add(target)
            _LOGGER.warning("Exception reading %s: %s", target, exc)

    def _log_read_ok(self, target: str) -> None:
        """Re-arm the warn-once log for a target that reads fine again."""
        if target in self._read_failures_warned:
            self._read_failures_warned.discard(target)
            _LOGGER.info("Reading %s recovered", target)

    def _mark_disconnected(self) -> None:
        """Drop the connection after a link failure so the next poll reconnects.

        pymodbus' connect() replaces the transport without closing the old
        one, so the transport is closed here before any reconnect.
        """
        self._connected = False
        with contextlib.suppress(Exception):
            self._client.close()

    async def connect(self) -> bool:
        """Connect to the Modbus server."""
        if not self._connected:
            self._connected = await self._client.connect()
            if self._connected:
                self._backoff_seconds = 0.0
                self._next_connect_at = 0.0
        return self._connected

    @property
    def is_connected(self) -> bool:
        """Return True if connected."""
        return self._connected

    async def _ensure_connected(self) -> None:
        """Ensure connection is active, reconnecting with backoff if needed."""
        if self._connected:
            return

        now = time.monotonic()
        if now < self._next_connect_at:
            return

        result = await self._client.connect()
        if result:
            self._connected = True
            self._backoff_seconds = 0.0
            self._next_connect_at = 0.0
        else:
            self._backoff_seconds = min(
                self._backoff_max, max(1.0, self._backoff_seconds * 2)
            )
            self._next_connect_at = now + self._backoff_seconds

    async def close(self) -> None:
        """Close connection."""
        self._client.close()
        self._connected = False
        self._backoff_seconds = 0.0
        self._next_connect_at = 0.0

    async def get_all_data(self) -> QubeState | None:
        """Fetch all definition data and return a state object.

        This fetches core sensors for the official HA integration.
        Returns None if not connected and reconnection fails, or if the
        connection was lost during this poll.
        """
        await self._ensure_connected()
        if not self._connected:
            return None

        state = QubeState()

        # Batch-read the core sensor fields plus all binary sensors together.
        # _plan_blocks groups by input type (input/holding/discrete_input/coil)
        # regardless of which list an entity came from, so combining both
        # tables into a single read_entities_batched() call still yields one
        # handful of block transactions instead of ~59 per-field reads.
        entities = [*_CORE_STATE_ENTITIES, *BINARY_SENSORS.values()]
        results = await self.read_entities_batched(entities)
        if not self._connected:
            return None

        for ent in _CORE_STATE_ENTITIES:
            setattr(state, ent.key, results.get(ent.key))

        flow_rate = state.flow_rate
        if flow_rate is not None and flow_rate < 0:
            flow_rate = 0.0
        state.flow_rate = flow_rate

        self._apply_monotonic_clamping(state)

        for key in BINARY_SENSORS:
            if hasattr(state, key):
                setattr(state, key, results.get(key))

        # Compute unified status (status_code + anti-legionella override)
        state.status = const.resolve_status(state.status_code, state.req_antileg_1)

        return state

    @property
    def monotonic_cache(self) -> dict[str, float]:
        """Return the monotonic clamping cache.

        Can be used to persist/restore the cache across restarts.
        """
        return self._monotonic_cache

    @monotonic_cache.setter
    def monotonic_cache(self, value: dict[str, float]) -> None:
        """Set the monotonic clamping cache (e.g. restored from disk)."""
        self._monotonic_cache = dict(value)
        self._monotonic_reset_pending.clear()

    def clear_monotonic_cache(self) -> None:
        """Forget all monotonic baselines.

        The next reading of every counter is accepted as-is. Use this when
        the controller's counters were reset on purpose and the clamped
        values in the cache are known to be stale.
        """
        self._monotonic_cache.clear()
        self._monotonic_reset_pending.clear()

    # A drop below the cached maximum larger than this (in the counter's own
    # unit: kWh for the energy totals) is treated as a counter reset rather
    # than float32 jitter or a transient glitch...
    MONOTONIC_RESET_THRESHOLD: float = 1.0
    # ...but only after it has been seen on this many consecutive reads, so a
    # single glitched zero read never drops a total_increasing counter.
    MONOTONIC_RESET_CONFIRM_READS: int = 3

    def clamp_monotonic(
        self,
        key: str,
        value: float | None,
        reset_threshold: float | None = None,
    ) -> float | None:
        """Clamp a value to prevent decreases for total_increasing counters.

        If the new value is lower than the previously seen value for this
        key by less than ``reset_threshold``, the previous value is returned
        (jitter suppression). A larger drop is a counter-reset candidate: it
        is still clamped until it has persisted for
        ``MONOTONIC_RESET_CONFIRM_READS`` consecutive reads, after which the
        low value is accepted as the new baseline and a warning is logged.
        None and non-finite values pass through unchanged and do not affect
        the reset detection.

        Args:
            key: Identifier for this counter (e.g. entity unique_id).
            value: The current reading.
            reset_threshold: Drop size that counts as a reset; defaults to
                ``MONOTONIC_RESET_THRESHOLD``.

        Returns:
            The clamped value, or None if input was None/non-finite.
        """
        if value is None or not math.isfinite(value):
            return value
        previous = self._monotonic_cache.get(key)
        if previous is None or value >= previous:
            self._monotonic_cache[key] = value
            self._monotonic_reset_pending.pop(key, None)
            return value

        threshold = (
            self.MONOTONIC_RESET_THRESHOLD
            if reset_threshold is None
            else reset_threshold
        )
        if previous - value < threshold:
            # Sub-threshold jitter: clamp and forget any pending reset
            self._monotonic_reset_pending.pop(key, None)
            return previous

        pending = self._monotonic_reset_pending.get(key, 0) + 1
        if pending < self.MONOTONIC_RESET_CONFIRM_READS:
            self._monotonic_reset_pending[key] = pending
            return previous

        _LOGGER.warning(
            "Counter reset detected for %s: value dropped from %s to %s on %d "
            "consecutive reads; accepting it as the new baseline",
            key,
            previous,
            value,
            pending,
        )
        self._monotonic_reset_pending.pop(key, None)
        self._monotonic_cache[key] = value
        return value

    _MONOTONIC_KEYS = frozenset({"energy_total_electric", "energy_total_thermic"})

    def _apply_monotonic_clamping(self, state: QubeState) -> None:
        """Apply monotonic clamping to energy counters in a QubeState."""
        for key in self._MONOTONIC_KEYS:
            current = getattr(state, key, None)
            clamped = self.clamp_monotonic(key, current)
            if clamped is not current:
                setattr(state, key, clamped)

    async def async_get_software_version(self) -> str | None:
        """Read the software version from the device.

        Reads InputRegister 77 (GeneralMng.Softversion).

        Returns:
            Version as string (e.g., "2.15"), or None on error.
        """
        value = await self.read_value(const.SOFTWARE_VERSION)
        if value is None:
            return None
        return f"{value:.2f}"

    async def get_all_entities(self) -> dict[str, Any]:
        """Fetch all entity values from library definitions.

        This reads all sensors, binary sensors, and switches defined in the
        library's entity definitions. Used by the HACS integration.

        Returns:
            Dictionary mapping entity keys to their values.
        """
        all_entities = [
            *SENSORS.values(),
            *BINARY_SENSORS.values(),
            *SWITCHES.values(),
        ]
        return await self.read_entities_batched(all_entities)

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
            # Qube uses Big Endian word order (ABCD format):
            # regs[0] = MSW (Most Significant Word)
            # regs[1] = LSW (Least Significant Word)
            # 32-bit value = (regs[0] << 16) | regs[1]

            if data_type == const.DataType.FLOAT32:
                # Combine 2 registers, Big Endian Word Order
                int_val = (regs[0] << 16) | regs[1]
                val = struct.unpack(">f", struct.pack(">I", int_val))[0]
            elif data_type == const.DataType.INT16:
                val = regs[0]
                # Signed 16-bit
                if val > 32767:
                    val -= 65536
            elif data_type == const.DataType.UINT16:
                val = regs[0]
            elif data_type == const.DataType.UINT32:
                int_val = (regs[0] << 16) | regs[1]
                val = int_val
            elif data_type == const.DataType.INT32:
                int_val = (regs[0] << 16) | regs[1]
                val = int_val
                if val > 2147483647:
                    val -= 4294967296
            else:
                val = 0

            if scale is not None:
                val *= scale
            if offset is not None:
                val += offset

            self._log_read_ok(f"address {address}")
            return val

        except Exception as e:
            self._log_read_failure(f"address {address}", e)
            if isinstance(e, _LINK_ERRORS):
                self._mark_disconnected()
            return None

    @staticmethod
    def _register_count(entity: EntityDef) -> int:
        """Return the number of registers an entity occupies."""
        data_type_str = entity.data_type.value if entity.data_type else None
        return 2 if data_type_str in ("float32", "uint32", "int32") else 1

    @staticmethod
    def _decode_registers(data_type_str: str | None, regs: list[int]) -> float | int:
        """Decode raw registers based on data type.

        Qube uses big endian word order (ABCD): regs[0]=MSW, regs[1]=LSW.
        """
        val: float | int = 0
        if data_type_str == "float32":
            int_val = (regs[0] << 16) | regs[1]
            val = struct.unpack(">f", struct.pack(">I", int_val))[0]
        elif data_type_str == "int16":
            val = regs[0]
            if val > 32767:
                val -= 65536
        elif data_type_str == "uint16":
            val = regs[0]
        elif data_type_str == "uint32":
            int_val = (regs[0] << 16) | regs[1]
            val = int_val
        elif data_type_str == "int32":
            int_val = (regs[0] << 16) | regs[1]
            val = int_val
            if val > 2147483647:
                val -= 4294967296
        return val

    @staticmethod
    def _apply_scaling(entity: EntityDef, val: float | int) -> float | int:
        """Apply an entity's scale, offset and precision to a raw value."""
        if entity.scale is not None:
            val = val * entity.scale
        if entity.offset is not None:
            val = val + entity.offset
        if entity.precision is not None and isinstance(val, float):
            val = round(val, entity.precision)
        return val

    def _plan_blocks(
        self, entities: Iterable[EntityDef]
    ) -> list[tuple[str, int, int, list[EntityDef]]]:
        """Group entities into contiguous block reads per input type.

        Returns a list of (input_type, start_address, count, entities)
        tuples. Entities within _MAX_GAP_* of each other share a block.
        """
        groups: dict[str, list[EntityDef]] = {}
        for ent in entities:
            input_type_str = ent.input_type.value if ent.input_type else "holding"
            groups.setdefault(input_type_str, []).append(ent)

        blocks: list[tuple[str, int, int, list[EntityDef]]] = []
        for input_type_str, ents in groups.items():
            is_bits = input_type_str in ("coil", "discrete_input")
            max_gap = self._MAX_GAP_BITS if is_bits else self._MAX_GAP_REGISTERS
            max_block = self._MAX_BLOCK_BITS if is_bits else self._MAX_BLOCK_REGISTERS
            start: int | None = None
            end = 0
            members: list[EntityDef] = []
            for ent in sorted(ents, key=lambda e: e.address):
                count = 1 if is_bits else self._register_count(ent)
                ent_end = ent.address + count
                if start is None:
                    start, end, members = ent.address, ent_end, [ent]
                elif ent.address <= end + max_gap and ent_end - start <= max_block:
                    end = max(end, ent_end)
                    members.append(ent)
                else:
                    blocks.append((input_type_str, start, end - start, members))
                    start, end, members = ent.address, ent_end, [ent]
            if start is not None:
                blocks.append((input_type_str, start, end - start, members))
        return blocks

    async def read_entities_batched(
        self, entities: Iterable[EntityDef]
    ) -> dict[str, Any]:
        """Read entities using contiguous block reads.

        Groups entities into a handful of Modbus block reads instead of
        one transaction per entity. If a block read fails, its entities
        are read individually as a fallback. If one of those single reads
        hits a link failure (no connection, no response), the device is
        treated as unreachable: the client is marked disconnected and the
        remaining reads are skipped.

        Returns:
            Dictionary mapping every requested entity key to its value
            (None on error).
        """
        results: dict[str, Any] = {}
        blocks = self._plan_blocks(entities)
        for input_type_str, start, count, members in blocks:
            target = f"block {input_type_str}@{start} (count {count})"
            try:
                result = await self._read_block(input_type_str, start, count)
            except Exception as exc:
                self._log_read_failure(target, exc)
                if not await self._read_individually(members, results):
                    self._mark_disconnected()
                    for _, _, _, block_members in blocks:
                        for ent in block_members:
                            results.setdefault(ent.key, None)
                    return results
                continue

            self._log_read_ok(target)
            for ent in members:
                offset = ent.address - start
                if input_type_str in ("coil", "discrete_input"):
                    results[ent.key] = bool(result.bits[offset])
                else:
                    reg_count = self._register_count(ent)
                    regs = result.registers[offset : offset + reg_count]
                    data_type_str = ent.data_type.value if ent.data_type else None
                    val = self._decode_registers(data_type_str, regs)
                    results[ent.key] = self._apply_scaling(ent, val)
        return results

    async def _read_block(self, input_type_str: str, start: int, count: int) -> Any:
        """Read one block and validate the response.

        Raises:
            _BlockReadError: On a Modbus error reply or a short response.
            Any of _LINK_ERRORS: When the device could not be reached.
        """
        if input_type_str == "coil":
            result = await self._client.read_coils(
                start, count=count, device_id=self.unit
            )
        elif input_type_str == "discrete_input":
            result = await self._client.read_discrete_inputs(
                start, count=count, device_id=self.unit
            )
        elif input_type_str == "input":
            result = await self._client.read_input_registers(
                start, count=count, device_id=self.unit
            )
        else:  # holding
            result = await self._client.read_holding_registers(
                start, count=count, device_id=self.unit
            )
        if result.isError():
            raise _BlockReadError(f"Modbus error response for block @{start}")
        if input_type_str in ("coil", "discrete_input"):
            if len(result.bits) < count:
                raise _BlockReadError(
                    f"Short bit response for block {input_type_str}@{start} "
                    f"(got {len(result.bits)}, expected {count})"
                )
        elif len(result.registers) < count:
            raise _BlockReadError(
                f"Short register response for block {input_type_str}@{start} "
                f"(got {len(result.registers)}, expected {count})"
            )
        return result

    async def _read_individually(
        self, members: list[EntityDef], results: dict[str, Any]
    ) -> bool:
        """Read a failed block's entities one by one into ``results``.

        Returns False as soon as a read hits a link failure, so a dead
        device costs one extra transaction instead of one per entity.
        """
        for ent in members:
            try:
                results[ent.key] = await self._read_entity_or_raise(ent)
            except _LINK_ERRORS as exc:
                self._log_read_failure(f"entity {ent.key}", exc)
                return False
            except Exception as exc:
                self._log_read_failure(f"entity {ent.key}", exc)
                results[ent.key] = None
        return True

    async def read_entity(self, entity: EntityDef) -> Any:
        """Read a single entity value based on EntityDef.

        Args:
            entity: The entity definition to read.

        Returns:
            The read value (float, int, or bool depending on entity type).
        """
        try:
            return await self._read_entity_or_raise(entity)
        except Exception as e:
            self._log_read_failure(f"entity {entity.key}", e)
            if isinstance(e, _LINK_ERRORS):
                self._mark_disconnected()
            return None

    async def _read_entity_or_raise(self, entity: EntityDef) -> Any:
        """Read a single entity; return None on an error reply, raise otherwise."""
        # Determine register count based on data type
        # Use string comparison to handle potential enum class differences
        data_type_str = entity.data_type.value if entity.data_type else None
        count = self._register_count(entity)

        # Read based on input type (use string comparison for safety)
        input_type_str = entity.input_type.value if entity.input_type else None

        if input_type_str == "coil":
            result = await self._client.read_coils(
                entity.address, count=1, device_id=self.unit
            )
            if result.isError():
                _LOGGER.warning("Error reading coil %s", entity.address)
                return None
            value: Any = bool(result.bits[0])
        elif input_type_str == "discrete_input":
            result = await self._client.read_discrete_inputs(
                entity.address, count=1, device_id=self.unit
            )
            if result.isError():
                _LOGGER.warning("Error reading discrete input %s", entity.address)
                return None
            value = bool(result.bits[0])
        else:
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

            val = self._decode_registers(data_type_str, result.registers)
            value = self._apply_scaling(entity, val)

        self._log_read_ok(f"entity {entity.key}")
        return value

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
            if isinstance(e, _LINK_ERRORS):
                self._mark_disconnected()
            return False

    # SG Ready mode API
    SG_READY_MODES = ("off", "block", "plus", "max")
    _SGREADY_MODE_TO_BITS: dict[str, tuple[bool, bool]] = {
        "off": (False, False),
        "block": (True, False),
        "plus": (False, True),
        "max": (True, True),
    }
    _SGREADY_BITS_TO_MODE: dict[tuple[bool, bool], str] = {
        v: k for k, v in _SGREADY_MODE_TO_BITS.items()
    }

    async def get_sg_ready_mode(self) -> str | None:
        """Read the current SG Ready mode.

        Returns:
            Mode string ("off", "block", "plus", "max"), or None on error.
        """
        bit_a = await self.read_switch("bms_sgready_a")
        bit_b = await self.read_switch("bms_sgready_b")
        if bit_a is None or bit_b is None:
            return None
        return self._SGREADY_BITS_TO_MODE.get((bool(bit_a), bool(bit_b)))

    async def set_sg_ready_mode(self, mode: str) -> bool:
        """Set the SG Ready mode.

        Args:
            mode: One of "off", "block", "plus", "max".

        Returns:
            True if both writes succeeded, False otherwise.
        """
        bits = self._SGREADY_MODE_TO_BITS.get(mode)
        if bits is None:
            _LOGGER.warning("Unknown SG Ready mode: %s", mode)
            return False
        success_a = await self.write_switch("bms_sgready_a", bits[0])
        success_b = await self.write_switch("bms_sgready_b", bits[1])
        return success_a and success_b

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
                # Big Endian word order: regs[0]=MSW, regs[1]=LSW
                packed = struct.pack(">f", write_value)
                int_val = struct.unpack(">I", packed)[0]
                regs = [(int_val >> 16) & 0xFFFF, int_val & 0xFFFF]
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
                _LOGGER.warning(
                    "Unsupported data type for writing: %s", entity.data_type
                )
                return False

            if result.isError():
                _LOGGER.warning("Error writing setpoint %s", key)
                return False
            return True

        except Exception as e:
            _LOGGER.error("Exception writing setpoint %s: %s", key, e)
            if isinstance(e, _LINK_ERRORS):
                self._mark_disconnected()
            return False
