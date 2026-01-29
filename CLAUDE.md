# Claude Code Instructions for python-qube-heatpump

This is an async Python library for communicating with Qube Heat Pumps via Modbus TCP.

## Project Structure

```
python-qube-heatpump/
├── src/python_qube_heatpump/
│   ├── __init__.py      # Exports QubeClient
│   ├── client.py        # Main QubeClient class with Modbus communication
│   ├── const.py         # Modbus register definitions (addresses, types, scales)
│   └── models.py        # QubeState dataclass with all sensor fields
├── tests/
│   ├── conftest.py      # Pytest fixtures for mocking Modbus client
│   └── test_client.py   # Unit tests for QubeClient
├── pyproject.toml       # Package configuration and dependencies
└── pytest.ini           # Pytest configuration
```

## Key Components

### QubeClient (client.py)
- Async Modbus TCP client using `pymodbus`
- `connect()` - Establish connection to heat pump
- `close()` - Close connection
- `get_all_data()` - Fetch all sensor values, returns `QubeState`
- `read_value(definition)` - Read a single register based on const definition

### QubeState (models.py)
Dataclass containing all sensor values:
- **Temperatures**: `temp_supply`, `temp_return`, `temp_source_in`, `temp_source_out`, `temp_room`, `temp_dhw`, `temp_outside`
- **Power/Energy**: `power_thermic`, `power_electric`, `energy_total_electric`, `energy_total_thermic`, `cop_calc`
- **Operation**: `status_code`, `compressor_speed`, `flow_rate`
- **Setpoints**: `setpoint_room_heat_day`, `setpoint_room_heat_night`, `setpoint_room_cool_day`, `setpoint_room_cool_night`, `setpoint_dhw`

### Register Definitions (const.py)
Each register is defined as: `(address, ModbusType, DataType, scale, offset)`
- `ModbusType`: `INPUT` or `HOLDING`
- `DataType`: `FLOAT32`, `INT16`, `UINT16`, `INT32`, `UINT32`

## Development Commands

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

### Run Tests
```bash
pytest tests/ -v
```

### Linting
```bash
pip install ruff
ruff check src/
ruff format src/
```

## Integration with Home Assistant

This library is used by the `qube_heatpump` integration in Home Assistant core:
- **Repo**: https://github.com/home-assistant/core
- **Integration path**: `homeassistant/components/qube_heatpump/`
- **Manifest requirement**: `python-qube-heatpump==<version>`

### Compatibility Requirements

When modifying `QubeState` or `get_all_data()`:
1. All fields in `QubeState` must be populated by `get_all_data()`
2. The Home Assistant integration's sensors depend on these field names
3. Test both repos together before releasing

### Testing with Home Assistant Integration

```bash
# Install library in editable mode in HA core venv
cd /path/to/home-assistant/core
source venv/bin/activate
pip install -e /path/to/python-qube-heatpump

# Run integration tests
pytest tests/components/qube_heatpump --cov=homeassistant.components.qube_heatpump
```

## Versioning and Release

1. Update version in `pyproject.toml`
2. Commit changes
3. Create and push tag: `git tag -a v1.x.x -m "Release 1.x.x" && git push origin main --tags`
4. GitHub Action automatically publishes to PyPI on tag push
5. Update Home Assistant integration's `manifest.json` to require new version

## Code Style

- Use async/await for all I/O operations
- Type hints on all functions
- Docstrings for public methods
- Follow ruff formatting rules

---

## Architecture Design Decisions (HACS → Official HA Transition)

This section documents architectural decisions made to ensure smooth transition between:
- **HACS integration**: `~/Github/qube_heatpump` (feature-complete with ~400 entities)
- **Official HA integration**: `~/Github/core/homeassistant/components/qube_heatpump/` (currently sensors only)

### 1. Entity Definitions Location

**Decision**: Hybrid approach - library defines protocol-level properties, integration adds HA-specific metadata.

**Library (`python-qube-heatpump`) defines**:
- `key`: Unique identifier (e.g., `"temp_supply"`)
- `name`: Human-readable name
- `address`: Modbus register/coil address
- `input_type`: COIL, DISCRETE_INPUT, INPUT_REGISTER, HOLDING_REGISTER
- `data_type`: FLOAT32, INT16, UINT16, etc. (None for boolean types)
- `unit`: Standard units (°C, kWh, W, %, L/min)
- `scale`, `offset`: Protocol-level value transformations
- `platform`: SENSOR, BINARY_SENSOR, SWITCH
- `writable`: Boolean for write capability

**Integration adds**:
- `device_class`, `state_class`: HA-specific semantics
- `suggested_display_precision`: Display formatting
- `entity_category`, `translation_key`, `icon`: HA presentation

**Rationale**: Keeps library reusable for non-HA applications while centralizing ~400 entity definitions.

### 2. Entity Organization in Library

**Decision**: Platform-based modules

```
src/python_qube_heatpump/
├── entities/
│   ├── __init__.py          # Exports all entities + combined registry
│   ├── base.py              # EntityDef dataclass + enums
│   ├── sensors.py           # ~300 sensor definitions
│   ├── binary_sensors.py    # ~50 binary sensor definitions
│   └── switches.py          # ~20 switch definitions
```

**Rationale**: Mirrors HA platform organization, easier maintenance.

### 3. EntityDef Dataclass Structure

```python
@dataclass(frozen=True)
class EntityDef:
    """Definition of a Qube heat pump entity."""

    # Identity
    key: str                              # Unique identifier
    name: str                             # Human-readable name

    # Modbus specifics
    address: int                          # Register/coil address
    input_type: InputType                 # COIL, DISCRETE_INPUT, INPUT_REGISTER, HOLDING_REGISTER
    data_type: DataType | None = None     # FLOAT32, INT16, etc. (None for coils)

    # Platform hint
    platform: Platform                    # SENSOR, BINARY_SENSOR, SWITCH

    # Value transformation
    scale: float | None = None
    offset: float | None = None

    # Unit (protocol-level)
    unit: str | None = None               # "°C", "kWh", "W", "%", "L/min"

    # Write capability
    writable: bool = False
```

### 4. QubeClient API Methods

**Decision**: Type-specific methods for clarity and type safety.

```python
# Reading
async def read_sensor(self, entity: EntityDef) -> float | int | None
async def read_binary_sensor(self, entity: EntityDef) -> bool | None
async def read_switch_state(self, entity: EntityDef) -> bool | None

# Writing
async def write_switch(self, entity: EntityDef, value: bool) -> None
async def write_setpoint(self, entity: EntityDef, value: float) -> None

# Bulk operations
async def get_all_data(self) -> QubeState  # Backward compatible
async def read_entities(self, entities: list[EntityDef]) -> dict[str, Any]
```

### 5. QubeState Model Strategy

**Decision**: Keep typed fields for core sensors, add `_extended` dict for additional entities.

```python
@dataclass
class QubeState:
    """State of the Qube Heat Pump."""

    # Core sensors (official HA integration uses these directly)
    temp_supply: float | None = None
    temp_return: float | None = None
    # ... all existing 18 fields ...

    # Extended data for additional HACS entities
    _extended: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key, checking typed fields first, then extended."""
        if hasattr(self, key) and not key.startswith('_'):
            val = getattr(self, key)
            if val is not None:
                return val
        return self._extended.get(key, default)
```

**Transition workflow (HACS → Official)**:
1. HACS uses `state.get("new_sensor")` for extended entities
2. When promoting to official: add typed field to `QubeState`
3. Official integration uses `state.new_sensor` directly
4. No breaking changes - both integrations work with same library version

### 6. Related Repositories

| Repository | Path | Purpose |
|------------|------|---------|
| python-qube-heatpump | `~/Github/python-qube-heatpump` | This library |
| HACS integration | `~/Github/qube_heatpump` | Feature-complete custom component |
| Official HA integration | `~/Github/core/homeassistant/components/qube_heatpump/` | Official HA core integration |

### 7. Testing Strategy

When making changes:
1. Run library tests: `pytest tests/ -v`
2. Install in HACS integration and test: `pip install -e ~/Github/python-qube-heatpump`
3. Install in HA core and test: `pytest tests/components/qube_heatpump -v`
4. Ensure no breaking changes to official integration's `QubeState` field access
