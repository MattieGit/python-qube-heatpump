# Repository Guidelines

Guidelines for coding agents and contributors working on `python-qube-heatpump`, the async Modbus/TCP
library for Qube heat pumps (HR-energy, Carel c.pCO controller). `CLAUDE.md` only imports this file;
keep everything here.

## Layout
- `src/python_qube_heatpump/client.py` — `QubeClient`: connection handling with backoff, batched block
  reads, monotonic clamping of the energy and working-hour counters, validated writes, SG Ready.
- `src/python_qube_heatpump/entities/` — the entity registry (`SENSORS`, `BINARY_SENSORS`, `SWITCHES`):
  one frozen `EntityDef` per register or coil (key, address, input type, data type, scale, unit,
  `writable`, `min_value`/`max_value`). `base.py` holds the dataclass and enums.
- `src/python_qube_heatpump/const.py` — register tuples for `read_value()` (e.g. `SOFTWARE_VERSION`),
  `StatusCode` and `resolve_status()`.
- `src/python_qube_heatpump/models.py` — `QubeState`, the typed snapshot returned by `get_all_data()`;
  the registers behind it are listed in `_CORE_STATE_ENTITIES` in `client.py`.
- `src/python_qube_heatpump/mdns.py` — `async_get_device_info()` / `parse_device_info()`: panel software
  version, controller firmware, project name and controller uuid from the `_workstation._tcp` mDNS
  record (Carel vendor `000A5C`).
- `src/python_qube_heatpump/network.py` — `async_get_mac_address()`.
- `docs/modbus-lijst-qube-totaal.pdf` — the vendor register list (Dutch).
- Public API: everything in `__init__.py` `__all__`; keep it backward compatible within a major version.

## Consumers
- **HACS integration** (`~/Github/qube_heatpump`, domain `qube_heatpump`): pins `>=`; uses
  `get_all_entities()`, `write_switch()`, `write_setpoint()`, the monotonic cache helpers,
  `async_get_software_version()`, `async_verify_device()` and the mDNS helpers. The library entity key
  becomes the integration's entity id suffix, so never rename a key.
- **Home Assistant core** (`homeassistant/components/hr_energy_qube`): pins `==`, so every release
  needs a bump PR in core; uses `get_all_data()`, `read_all_switches()`, `get_sg_ready_mode()`,
  `async_get_software_version()`, `async_verify_device()` and the mDNS helpers.
- A behaviour change in an existing method can break core's config flow or entities; check both
  consumers before releasing (for example, 1.16.1 made a 0 software-version register return `None`,
  which is why core validates with `async_verify_device()`).

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -e ".[test]"`.
- Tests: `pytest` (CI runs Python 3.12, 3.13 and 3.14).
- Lint/format: `ruff check .` and `ruff format --check .`. CI pins ruff 0.14.14 (`uvx ruff@0.14.14`);
  newer ruff defaults reformat the repo.

## Releases
- Bump `version` in `pyproject.toml` in the PR (semantic versioning).
- After merge: `gh release create vX.Y.Z --target main` publishes to PyPI through
  `.github/workflows/python-publish.yml` (trusted publishing). Watch the workflow run, not only PyPI;
  a run that was never picked up by a runner uploaded nothing and can be re-run.
- Then raise the pin in the HACS integration and open a bump PR in core.

## Commits
- Imperative subject lines; reference the version in release PRs (e.g. `... (v1.17.0)`).
- No AI attribution or co-author trailers.
