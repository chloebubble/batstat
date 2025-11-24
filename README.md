# batstat

A beautiful battery status display for macOS that provides detailed information about your MacBook's battery health and power status.

## Requirements

- macOS (uses `pmset` and `system_profiler` for battery information)
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

### Fish helper (`gacp`)

The repo includes a useful Fish helper that stages, commits, and pushes with optional auto-generated messages.

1. Symlink it into your Fish functions directory:
   ```bash
   mkdir -p ~/.config/fish/functions
   ln -sf (pwd)/scripts/fish/gacp.fish ~/.config/fish/functions/gacp.fish
   ```
2. Run `gacp` from any git repo. Flags:
   - `-a/--auto` (default) builds a Conventional Commit-style subject from staged changes
   - `--codex` asks the Codex CLI to generate the subject; use `--codex-model <model>` to pick a model
   - `-m/--message` supplies your own message; `-e/--edit` opens `$EDITOR` to tweak it
   - `-n/--dry-run` previews the git commands; `-v/--verbose` echoes them as they run
   - `-r/--remote` and `-b/--branch` override the push target (defaults: `origin` + current branch)
   - `-y/--yes` skips confirmation prompts; `--no-verify` passes through to git commit/push

Environment defaults: `GACP_REMOTE` and `GACP_BRANCH`.

## Usage

### Basic usage

Display full battery status with colors and formatting:

```bash
# From the repo (no install):
uv run bat

# After editable install:
uvx bat
```

### Running with Rich library

For the best visual experience with beautiful tables and colors, run with Rich explicitly:

```bash
# Temporarily add Rich dependency just for this run:
uv run --with rich bat

# Or ensure Rich is available in your environment:
uv sync --with rich
uv run bat
```

**Why use `--with rich`?**
- The script works without Rich (graceful fallback to basic text)
- Adding `--with rich` gives you beautiful formatted tables and panels
- Keeps dependencies minimal while allowing enhanced output when desired

### Features

- **Rich Display**: Beautiful tables and colors when Rich library is available
- **Graceful Fallback**: Plain text output with basic ANSI colors when Rich isn't installed
- **Comprehensive Data**: Combines `pmset`, `system_profiler`, and `ioreg` to fill gaps (design/full/charge mAh, health %, live watts, temperature)
- **Cross-platform**: Works on any macOS system without additional dependencies
- **Flexible Dependencies**: Choose between minimal setup or rich visualization

### Help

Show all available options:
```bash
uv run bat --help
```

## Output Information

The tool displays:

- **Battery Status**: Current charge percentage, charging state, and time remaining
- **Battery Health**: Health text plus percent of design capacity, cycle count, current/full/design capacity (mAh)
- **Power Details**: Voltage, amperage, live charging power in watts, and battery temperature (°C)
- **Adapter Information**: Charger connection status, rated wattage, manufacturer, and serial number
- **Raw Data**: Original `pmset` output for reference

## Sample Output

### With Rich Library (recommended)

The tool displays beautiful formatted tables with color-coded battery levels and health status:

- 🔋 Battery percentage with color coding (green ≥80%, yellow ≥40%, red <40%)
- 📊 Detailed battery and adapter information in separate tables
- 🧮 Health % based on full vs design capacity, plus live charging watts and temperature
- 📋 Raw `pmset` output panel for debugging

### Without Rich Library

Clean text output with ANSI color coding and clear formatting.

## Development

The project uses uv for dependency management. To modify or extend:

```bash
# Install base dependencies
uv sync

# Run with Rich (recommended for development):
uv run --with rich bat

# Run without Rich (minimal dependencies):
uv run bat

# Test fallback mode without uv:
python3 bat.py

# Install in development mode with Rich:
uv install -e . --with rich

# Run tests (if any):
uv run pytest
```

## Project Structure

```
batstat/
├── bat.py                  # Main CLI + battery logic (entrypoint: bat:main)
├── batstat                 # Fish helper to run `uv run --with rich bat`
├── pyproject.toml          # Project configuration (uv / setuptools metadata)
├── README.md               # This file
└── uv.lock                 # Locked dependency versions (tracked)
```

## Technical Details

This script uses:

- **`pmset -g batt`**: Live battery status, percentage, charging state, and time estimates
- **`system_profiler SPPowerDataType -json`**: Battery health info and charger specifications
- **`ioreg -rd1 -c AppleSmartBattery`**: Real-time metrics (charge/full/design capacity, voltage, amperage, temperature, live watts)
- **Rich Library** (optional): For beautiful terminal output with tables and panels
- **Graceful degradation**: Full functionality without Rich using basic ANSI colors

The script automatically detects Rich availability and provides the best possible output format for your environment.
