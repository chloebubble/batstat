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
uvx batstat
```

### Features

- **Rich Display**: Beautiful tables and colors when Rich library is available
- **Graceful Fallback**: Plain text output with basic ANSI colors when Rich isn't installed
- **Comprehensive Data**: Uses both `pmset` for live status and `system_profiler` for detailed health/charger info
- **Cross-platform**: Works on any macOS system without additional dependencies

### Help

Show all available options:
```bash
uv run bat --help
```

## Output Information

The tool displays:

- **Battery Status**: Current charge percentage, charging state, and time remaining
- **Battery Health**: Health status (Normal/Fair/Service), cycle count, and capacity details
- **Power Details**: Voltage and amperage information
- **Adapter Information**: Charger connection status, wattage, manufacturer, and serial number
- **Raw Data**: Original `pmset` output for reference

## Sample Output

### With Rich Library (recommended)

The tool displays beautiful formatted tables with color-coded battery levels and health status:

- 🔋 Battery percentage with color coding (green ≥80%, yellow ≥40%, red <40%)
- 📊 Detailed battery and adapter information in separate tables
- 📋 Raw `pmset` output panel for debugging

### Without Rich Library

Clean text output with ANSI color coding and clear formatting.

## Development

The project uses uv for dependency management. To modify or extend:

```bash
# Install dependencies
uv sync

# Run the script directly
uv run bat

# Install in development mode
uv install -e .

# Test without Rich (fallback mode)
python3 bat.py
```

## Project Structure

```
batstat/
├── bat.py                # Main standalone script
├── pyproject.toml        # Project configuration
├── scripts/fish/gacp.fish # Git helper utility
└── README.md             # This file
```

## Technical Details

This script uses:

- **`pmset -g batt`**: Live battery status, percentage, charging state, and time estimates
- **`system_profiler SPPowerDataType -json`**: Detailed battery health information and charger specifications
- **Rich Library** (optional): For beautiful terminal output with tables and panels
- **Graceful degradation**: Full functionality without Rich using basic ANSI colors

The script automatically detects Rich availability and provides the best possible output format for your environment.
