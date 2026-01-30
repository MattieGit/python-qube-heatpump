"""Models for Qube Heat Pump."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QubeState:
    """Representation of the Qube Heat Pump state.

    Typed fields for core sensors (used by official HA integration).
    Extended dict for additional entities (used by HACS integration).
    """

    # Temperatures
    temp_supply: float | None = None
    temp_return: float | None = None
    temp_source_in: float | None = None
    temp_source_out: float | None = None
    temp_room: float | None = None
    temp_dhw: float | None = None
    temp_outside: float | None = None

    # Power/Energy
    power_thermic: float | None = None
    power_electric: float | None = None
    energy_total_electric: float | None = None
    energy_total_thermic: float | None = None
    cop_calc: float | None = None

    # Operation
    status_code: int | None = None
    compressor_speed: float | None = None
    flow_rate: float | None = None

    # Setpoints (Read/Write)
    setpoint_room_heat_day: float | None = None
    setpoint_room_heat_night: float | None = None
    setpoint_room_cool_day: float | None = None
    setpoint_room_cool_night: float | None = None
    setpoint_dhw: float | None = None

    # Extended dict for additional entities not covered by typed fields
    _extended: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by key, checking typed fields first, then _extended."""
        if hasattr(self, key) and key != "_extended":
            value = getattr(self, key)
            return value if value is not None else default
        return self._extended.get(key, default)

    def set_extended(self, key: str, value: Any) -> None:
        """Set a value in the extended dict."""
        self._extended[key] = value
