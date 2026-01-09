# batstat

A macOS CLI tool for detailed battery health and power status.

## Requirements

- macOS
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

## Installation

```bash
git clone <repository-url>
cd batstat
uv sync
```

## Usage

```bash
# Basic output
uv run bat

# With Rich formatting (recommended)
uv run --with rich bat

# Show raw pmset output
uv run bat --raw
```

## What it shows

- **Battery**: charge %, health, cycle count, capacity (current/full/design mAh), voltage, amperage, temperature
- **Adapter**: connection status, wattage, live charging power, manufacturer info

Data is collected from `pmset`, `system_profiler`, and `ioreg`.

## Output

With Rich installed, you get formatted tables with color-coded status. Without Rich, you get plain text with ANSI colors.
