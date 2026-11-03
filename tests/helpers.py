"""Helpers shared by the QubeClient tests."""

import struct
from collections.abc import Sequence

from modbus_connection.mock import MockModbusUnit


def float32_regs(value: float) -> list[int]:
    """Encode a float32 as two registers, big-endian word order (MSW first)."""
    (raw,) = struct.unpack(">I", struct.pack(">f", value))
    return [raw >> 16, raw & 0xFFFF]


def float_from_regs(regs: Sequence[int]) -> float:
    """Decode two big-endian-word-order registers as a float32."""
    return struct.unpack(">f", struct.pack(">I", (regs[0] << 16) | regs[1]))[0]


def script_reads(
    unit: MockModbusUnit,
    method: str,
    *outcomes: BaseException | list[int] | list[bool] | None,
) -> None:
    """Script the next calls of one read method of ``unit``.

    Each call still goes through the in-memory unit (it connects and is
    recorded in ``read_events``), then the next outcome applies: an exception
    is raised, a list replaces the values read (for example a short
    response), and None keeps them. Later calls behave normally.
    """
    original = getattr(unit, method)
    pending = list(outcomes)

    async def read(address: int, count: int) -> list[int] | list[bool]:
        values = await original(address, count)
        if not pending:
            return values
        outcome = pending.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return values if outcome is None else outcome

    setattr(unit, method, read)
