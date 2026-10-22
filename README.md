# Python Qube Heat Pump Client

Asyncio client for HR-energy Qube heat pumps via Modbus TCP. It powers the
[Qube heat pump integration in Home Assistant](https://www.home-assistant.io/integrations/hr_energy_qube).

## Installation

```bash
pip install python-qube-heatpump
```

Requires Python 3.12 or newer.

## Usage

```python
import asyncio
from python_qube_heatpump import QubeClient

async def main():
    client = QubeClient("192.168.1.100", port=502, unit_id=1)
    if not await client.connect():
        raise SystemExit("Cannot reach the heat pump")

    state = await client.get_all_data()  # QubeState, or None when the connection failed
    if state:
        print(f"Status: {state.status}")
        print(f"Outside temp: {state.temp_outside}°C")
        print(f"Supply temp: {state.temp_supply}°C")
        print(f"DHW temp: {state.temp_dhw}°C")

    await client.close()

asyncio.run(main())
```

## Features

- **Async Modbus TCP client** using pymodbus, reconnecting with backoff after a lost connection
- **Batched reads**: `get_all_data()` and `get_all_entities()` read neighbouring registers in a handful of block transactions instead of one request per register
- **Entity definitions** for sensors, binary sensors, and switches
- **Validated writes**: `write_switch()`, and `write_setpoint()` within each register's `min_value`/`max_value`
- **SG Ready**: `get_sg_ready_mode()` / `set_sg_ready_mode()` with the modes `off`, `block`, `plus` and `max`
- **Unified status**: `QubeState.status` combines the status code with the anti-legionella request (`resolve_status()`)
- **FLOAT32 decoding** with big endian (ABCD) byte order
- **Typed**: ships `py.typed` and passes `mypy --strict`
- **Device verification**: `async_verify_device()` checks that a host answers like a Qube controller (register 77 readable, also when it reads 0 on recent firmware)
- **mDNS device information**: panel software version, controller firmware and UUID from the controller's advertisement
- **Monotonic clamping with reset detection** for the energy totals: sub-kWh jitter is clamped, while a drop of more than 1 kWh that persists for 3 consecutive reads is accepted as a counter reset (logged as a warning); `clear_monotonic_cache()` forgets all baselines

## Device information over mDNS

The controller advertises a `_workstation._tcp` mDNS service whose TXT record holds the software version shown on the panel, the controller firmware and a stable UUID. Register 77 (`async_get_software_version()`) reads 0.0 on recent firmware, so use this for the version instead:

```python
from zeroconf.asyncio import AsyncZeroconf
from python_qube_heatpump import async_get_device_info

aiozc = AsyncZeroconf()  # in Home Assistant: zeroconf.async_get_async_instance(hass)
info = await async_get_device_info("192.168.1.100", aiozc)
if info:
    print(info.software_version, info.controller_firmware, info.uuid)
```

The lookup returns `None` when no record is found within the timeout (default 5 s), for example when mDNS is not forwarded between VLANs. `parse_device_info(properties)` parses TXT properties you already have, such as those from a zeroconf discovery.

## Entity Definitions

The library provides pre-defined entity definitions for all Qube Modbus registers:

```python
from python_qube_heatpump.entities import SENSORS, BINARY_SENSORS, SWITCHES

# Access entity definitions by key
temp_supply = SENSORS["temp_supply"]
print(f"Address: {temp_supply.address}, Unit: {temp_supply.unit}")
```

## Vendor Documentation

The official Modbus register documentation from HR-Energy is available at:
- [docs/modbus-lijst-qube-totaal.pdf](docs/modbus-lijst-qube-totaal.pdf) (included in this repo)
- [HR-Energy website](https://www.hr-energy.com/media/rt4i0lmc/modbus-lijst-qube-totaal.pdf)

## Related Projects

- [Qube heat pump](https://www.home-assistant.io/integrations/hr_energy_qube) - Home Assistant core integration (`hr_energy_qube`), available without HACS
- [qube_heatpump](https://github.com/MattieGit/qube_heatpump) - Home Assistant custom integration (HACS) with extra features, such as a virtual thermostat and a DHW schedule

## License

MIT License
