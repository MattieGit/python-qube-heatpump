# Agents Instructions for python-qube-heatpump

## Overview

Async Python library for Qube Heat Pump communication via Modbus TCP. Used by the Home Assistant `qube_heatpump` integration.

## Quick Reference

| Item | Location |
|------|----------|
| Main client | `src/python_qube_heatpump/client.py` |
| Data model | `src/python_qube_heatpump/models.py` |
| Register definitions | `src/python_qube_heatpump/const.py` |
| Tests | `tests/test_client.py` |
| Version | `pyproject.toml` → `project.version` |

## Current Version: 1.2.3

### Recent Changes (1.2.3)
- `get_all_data()` now fetches all 21 sensor fields (previously only 4)
- Full compatibility with Home Assistant qube_heatpump integration

## Testing

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[test]"

# Run tests
pytest tests/ -v
```

## Adding New Sensors

1. **Add register definition** in `const.py`:
   ```python
   NEW_SENSOR = (address, ModbusType.INPUT, DataType.FLOAT32, scale, offset)
   ```

2. **Add field** to `QubeState` in `models.py`:
   ```python
   new_sensor: Optional[float] = None
   ```

3. **Fetch in `get_all_data()`** in `client.py`:
   ```python
   state.new_sensor = await _read(const.NEW_SENSOR)
   ```

4. **Update Home Assistant integration** to use the new field

## Data Types

| DataType | Registers | Notes |
|----------|-----------|-------|
| FLOAT32 | 2 | Little-endian word order |
| INT16 | 1 | Signed |
| UINT16 | 1 | Unsigned |
| INT32 | 2 | Little-endian word order |
| UINT32 | 2 | Little-endian word order |

## Related Repository

Home Assistant integration: `/Users/matthijskeij/Github/core/homeassistant/components/qube_heatpump/`

When making changes, test both repos together:
```bash
# In HA core repo
pip install -e /Users/matthijskeij/Github/python-qube-heatpump
pytest tests/components/qube_heatpump -v
```

## Release Checklist

- [ ] Update version in `pyproject.toml`
- [ ] Run tests: `pytest tests/ -v`
- [ ] Run linting: `ruff check src/ && ruff format --check src/`
- [ ] Commit and push
- [ ] Tag release: `git tag -a v1.x.x -m "Release message" && git push origin main --tags`
- [ ] Verify PyPI publish (GitHub Action)
- [ ] Update HA integration manifest.json with new version
- [ ] Run HA integration tests

---

## Architecture Decisions (Quick Reference)

See `CLAUDE.md` for detailed rationale.

### Entity Definitions
- **Library defines**: key, name, address, input_type, data_type, unit, scale, offset, platform, writable
- **Integration adds**: device_class, state_class, suggested_display_precision, translation_key, icon

### File Structure (Target)
```
src/python_qube_heatpump/
├── entities/
│   ├── __init__.py          # Combined registry
│   ├── base.py              # EntityDef dataclass
│   ├── sensors.py           # Sensor definitions
│   ├── binary_sensors.py    # Binary sensor definitions
│   └── switches.py          # Switch definitions
```

### QubeState Strategy
- Keep typed fields for core sensors (backward compatible with official HA)
- Add `_extended: dict` for additional HACS entities
- Use `state.get("key")` for extended entities
- Promote to typed field when moving to official HA

### QubeClient API
```python
# Type-specific reads
read_sensor(entity) -> float | int | None
read_binary_sensor(entity) -> bool | None
read_switch_state(entity) -> bool | None

# Writes
write_switch(entity, value: bool) -> None
write_setpoint(entity, value: float) -> None

# Bulk
get_all_data() -> QubeState  # Backward compatible
read_entities(entities) -> dict[str, Any]
```

### Related Repos
- HACS: `~/Github/qube_heatpump`
- Official HA: `~/Github/core/homeassistant/components/qube_heatpump/`
