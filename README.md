# batstat

A macOS CLI tool for detailed battery health and power status.

## Requirements

- macOS
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Optional (for iOS USB mode): `libimobiledevice` tools (`ideviceinfo`, `idevice_id`)
  - Install with Homebrew: `brew install libimobiledevice`

## Installation

```bash
git clone <repository-url>
cd batstat
uv sync
```

## Usage

```bash
# From the repo (no install):
uv run batstat

# After editable install:
uvx batstat
```

### Running with Rich library

For the best visual experience with beautiful tables and colors, run with Rich explicitly:

```bash
# Temporarily add Rich dependency just for this run:
uv run --with rich batstat

# Or ensure Rich is available in your environment:
uv sync --with rich
uv run batstat
```

## What it shows

- **Battery**: charge %, health, cycle count, capacity (current/full/design mAh), voltage, amperage, temperature
- **Adapter**: connection status, wattage, live charging power, manufacturer info

Data is collected from `pmset`, `system_profiler`, and `ioreg`.

With `--ios`, it reads available battery stats from a USB-connected iPhone/iPad.

## Output

Show all available options:
```bash
uv run batstat --help
```

Show raw output for debugging:
```bash
uv run batstat --raw
```

### iOS over USB

Read battery statistics from a USB-connected iPhone/iPad:

```bash
uv run batstat --ios
```

Show the raw iOS battery payload:

```bash
uv run batstat --ios --raw
```

If you have multiple devices connected, pass a UDID:

```bash
uv run batstat --ios --ios-udid <udid>
```

## Output Information

The tool displays:

- **Battery Status**: Current charge percentage, charging state, and time remaining
- **Battery Health**: Health text plus percent of design capacity, cycle count, current/full/design capacity (mAh)
- **Power Details**: Voltage, amperage, live charging power in watts, and battery temperature (°C)
- **Adapter Information**: Charger connection status, rated wattage, manufacturer, and serial number
- **Raw Data**: Original data source output for reference (use `--raw`)

When using `--ios`, it will show the iOS device battery percentage, charging state,
and any additional fields the device exposes (capacity, cycles, voltage, etc.).

## Sample Output

### With Rich Library (recommended)

The tool displays beautiful formatted tables with color-coded battery levels and health status:

- 🔋 Battery percentage with color coding (green ≥80%, yellow ≥40%, red <40%)
- 📊 Detailed battery and adapter information in separate tables
- 🧮 Health % based on full vs design capacity, plus live charging watts and temperature
- 📋 Raw `pmset` output panel for debugging (use `--raw`)

### Without Rich Library

Clean text output with ANSI color coding and clear formatting.

## Development

The project uses uv for dependency management. To modify or extend:

```bash
# Install base dependencies
uv sync

# Run with Rich (recommended for development):
uv run --with rich batstat

# Run without Rich (minimal dependencies):
uv run batstat

# Test fallback mode without uv:
python3 batstat.py

# Install in development mode with Rich:
uv install -e . --with rich

# Run tests (if any):
uv run pytest
```

## Project Structure

```
batstat/
├── batstat.py              # Main CLI + battery logic (entrypoint: batstat:main)
├── batstat                 # Fish helper to run `uv run --with rich batstat`
├── pyproject.toml          # Project configuration (uv / setuptools metadata)
├── README.md               # This file
└── uv.lock                 # Locked dependency versions (tracked)
```

## Technical Details

This script uses:

- **`pmset -g batt`**: Live battery status, percentage, charging state, and time estimates
- **`system_profiler SPPowerDataType -json`**: Battery health info and charger specifications
- **`ioreg -rd1 -c AppleSmartBattery`**: Real-time metrics (charge/full/design capacity, voltage, amperage, temperature, live watts)
- **`ideviceinfo -q com.apple.mobile.battery`**: iOS battery stats over USB (optional)
- **`idevice_id -l`**: List connected iOS devices (optional)
- **Rich Library** (optional): For beautiful terminal output with tables and panels
- **Graceful degradation**: Full functionality without Rich using basic ANSI colors

The script automatically detects Rich availability and provides the best possible output format for your environment.
