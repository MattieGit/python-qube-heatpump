"""Models for Qube Heat Pump."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class QubeState:
    """Representation of the Qube Heat Pump state."""

    # Temperatures
    temp_supply: Optional[float] = None
    temp_return: Optional[float] = None
    temp_source_in: Optional[float] = None
    temp_source_out: Optional[float] = None
    temp_room: Optional[float] = None
    temp_dhw: Optional[float] = None
    temp_outside: Optional[float] = None

    # Power/Energy
    power_thermic: Optional[float] = None
    power_electric: Optional[float] = None
    energy_total_electric: Optional[float] = None
    energy_total_thermic: Optional[float] = None
    cop_calc: Optional[float] = None

    # Operation
    status_code: Optional[int] = None
    compressor_speed: Optional[float] = None
    flow_rate: Optional[float] = None

    # Setpoints (Read/Write)
    setpoint_room_heat_day: Optional[float] = None
    setpoint_room_heat_night: Optional[float] = None
    setpoint_room_cool_day: Optional[float] = None
    setpoint_room_cool_night: Optional[float] = None
    setpoint_dhw: Optional[float] = None
