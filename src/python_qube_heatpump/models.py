"""Models for Qube Heat Pump."""

from dataclasses import dataclass, field
from typing import Any

from .const import StatusCode


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
    # Unified status combining status_code with req_antileg_1 override.
    # Computed by QubeClient.get_all_data(); see const.resolve_status().
    status: StatusCode | None = None
    compressor_speed: float | None = None
    flow_rate: float | None = None

    # Setpoints (Read/Write)
    setpoint_room_heat_day: float | None = None
    setpoint_room_heat_night: float | None = None
    setpoint_room_cool_day: float | None = None
    setpoint_room_cool_night: float | None = None
    setpoint_dhw: float | None = None

    # Binary sensors - Outputs
    dout_srcpmp_val: bool | None = None
    dout_usrpmp_val: bool | None = None
    dout_fourwayvlv_val: bool | None = None
    dout_cooling_val: bool | None = None
    dout_threewayvlv_val: bool | None = None
    dout_bufferpmp_val: bool | None = None
    dout_heaterstep1_val: bool | None = None
    dout_heaterstep2_val: bool | None = None
    dout_heaterstep3_val: bool | None = None

    # Binary sensors - System status
    keybonoff: bool | None = None
    daynightmode: bool | None = None

    # Binary sensors - Alarms
    al_maxtime_antileg_active: bool | None = None
    al_maxtime_dhw_active: bool | None = None
    al_dewpoint_active: bool | None = None
    al_underfloorsafety_active: bool | None = None
    alrm_flw: bool | None = None
    usralrms: bool | None = None
    coolingalrms: bool | None = None
    heatingalrms: bool | None = None
    alarmmng_al_workinghour: bool | None = None
    srsalrm: bool | None = None
    glbal: bool | None = None
    alarmmng_al_pwrplus: bool | None = None

    # Binary sensors - Sensor/controller status
    roomprb_en: bool | None = None
    plantprb_en: bool | None = None
    bufferprb_en: bool | None = None
    en_dhwpid: bool | None = None

    # Binary sensors - Demand signals
    plantdemand: bool | None = None
    id_demand: bool | None = None
    thermostatdemand: bool | None = None
    bms_demand: bool | None = None

    # Binary sensors - Digital inputs
    id_summerwinter: bool | None = None
    dewpoint: bool | None = None
    boostersecurity: bool | None = None
    srcflw: bool | None = None
    req_antileg_1: bool | None = None

    # Binary sensors - Energy
    surplus_pv: bool | None = None

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
