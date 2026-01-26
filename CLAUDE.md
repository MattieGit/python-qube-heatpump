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
