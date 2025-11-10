# batstat

A battery status display for macOS that provides detailed information about your MacBook's battery health and power status.

## Requirements

- macOS (uses `ioreg` and `system_profiler` for battery information)
- Python 3.11+
- uv (for package management)

## Installation

### Clone and run locally

```bash
git clone <repository-url>
cd batstat
uv sync
```

### Install as a package

```bash
uv install -e .
```

## Usage

### Basic usage

Display full battery status with colors and formatting:

```bash
# From the repo (no install):
uv run -m batstat

# After editable install or from PyPI:
uvx batstat
```

### Output modes

**Simple output** (script-friendly):
```bash
uv run -m batstat -s
uvx batstat -s
```

**JSON output** (for programmatic use):
```bash
uv run -m batstat -j
uvx batstat -j
```

This method uses both `ioreg` for battery data and `system_profiler` for accurate charger information including wattage and charger name.

**Disable colors** (for non-interactive terminals):
```bash
uv run -m batstat --no-color
uvx batstat --no-color
```

### Help

Show all available options:
```bash
uv run -m batstat --help
uvx batstat --help
```

## Output Information

The tool displays:

- **Battery Level**: Current charge percentage with status and progress bar
- **Battery Health**: Current capacity vs design capacity, cycle count
- **Power Details**: Voltage, current draw, temperature
- **Time Remaining**: Estimated time until full/empty
- **Power Adapter**: Charger name, wattage, and connection information when connected to power
- **System Info**: Battery serial number and last update time

## Simple Output Format

The `-s/--simple` option outputs one value per line:
```
62.0
Charging
95.0%
245
30.2�C
12.39V
1h 34m
�
```

Lines represent: percentage, status, health, cycles, temperature, voltage, time remaining, icon.

## JSON Output Format

The `-j/--json` option outputs structured data:
```json
{
  "percentage": 62.0,
  "health": 95.0,
  "status": "Charging",
  "icon": "�",
  "cycles": 245,
  "temperature_celsius": 30.25,
  "temperature_fahrenheit": 86.45,
  "voltage": 12.395,
  "amperage": 2155,
  "time_remaining": "1h 34m",
  "serial": "BATTERY_SERIAL",
  "adapter_name": "",
  "adapter_watts": 0,
  "charger_name": "61W USB-C Power Adapter",
  "charger_wattage": 60,
  "is_charging": true,
  "external_connected": true,
  "fully_charged": false,
  "updated_at": "2025-11-10T14:55:17.380196"
}
```

## Development

The project uses uv for dependency management. To modify or extend:

```bash
# Install dependencies
uv sync

# Run the script
uv run -m batstat

# Install in development mode
uv install -e .
```

## Project Structure

```
batstat/
├── src/batstat/          # Python package
│   ├── __init__.py       # Package initialization
│   └── batstat.py        # Main script
├── old/                  # Legacy scripts
│   ├── batstat           # Original fish script
│   ├── batstat.fish      # Fish function version
│   └── batstat.py.backup # Python backup
├── pyproject.toml        # Project configuration
└── README.md            # This file
```

## Migration from Fish Script

This Python version replaces the original `batstat.fish` script with:
- More robust error handling
- Multiple output formats (default, simple, JSON)
- Better data parsing using both `ioreg` and `system_profiler`
- Accurate charger wattage detection
- Package management with uv
- Type hints and cleaner code structure
- Proper ASCII formatting for universal compatibility

The original fish script and early Python versions are preserved in the `old/` directory for reference.
