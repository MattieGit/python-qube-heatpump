"""Switch entity definitions for Qube Heat Pump."""

from .base import EntityDef, InputType, Platform

_SWITCH_DEFS: tuple[EntityDef, ...] = (
    EntityDef(
        key="bms_summerwinter",
        name="Enable summer mode (cooling)",
        address=22,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="tapw_timeprogram_bms_forced",
        name="Start DHW heating",
        address=23,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="antilegionella_frcstart_ant",
        name="Start anti-legionella",
        address=45,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="en_plantsetp_compens",
        name="Enable heating curve",
        address=62,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="bms_sgready_a",
        name="SG Ready A",
        address=65,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="bms_sgready_b",
        name="SG Ready B",
        address=66,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
    EntityDef(
        key="modbus_demand",
        name="Activate heat demand",
        address=67,
        input_type=InputType.COIL,
        platform=Platform.SWITCH,
        writable=True,
    ),
)

# Export as dict for easy lookup by key
SWITCHES: dict[str, EntityDef] = {e.key: e for e in _SWITCH_DEFS}
