# Python Qube Heat Pump Client

Asyncio client for Qube heat pumps via Modbus TCP.

## Installation

```bash
pip install python-qube-heatpump
```

## Usage

```python
import asyncio
from python_qube_heatpump import QubeClient

async def main():
    client = QubeClient("192.168.1.100", port=502, unit_id=1)
    await client.connect()

    state = await client.read_state()
    print(f"Outside temp: {state.temp_outside}°C")
    print(f"Supply temp: {state.temp_supply}°C")
    print(f"DHW temp: {state.temp_dhw}°C")

    await client.disconnect()

asyncio.run(main())
```

## Features

- **Async Modbus TCP client** using pymodbus
- **Entity definitions** for sensors, binary sensors, and switches
- **FLOAT32 decoding** with big endian (ABCD) byte order
- **Type-safe dataclasses** for entity definitions
- **Monotonic clamping with reset detection** for the energy totals: sub-kWh jitter is clamped, while a drop of more than 1 kWh that persists for 3 consecutive reads is accepted as a counter reset (logged as a warning); `clear_monotonic_cache()` forgets all baselines

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

- [qube_heatpump](https://github.com/MattieGit/qube_heatpump) - Home Assistant HACS integration using this library

## License

MIT License
