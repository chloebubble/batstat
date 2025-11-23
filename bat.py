#!/usr/bin/env python3
"""
Pretty battery / charger overview for macOS.

- Uses `pmset -g batt` for live status.
- Uses `system_profiler SPPowerDataType -json` for health + charger info.
- Optional: `rich` for nice colours/tables (recommended).

Tested layout on macOS; key names are based on SPPowerDataType JSON schema.
"""

import json
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

# Optional pretty output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box

    HAS_RICH = True
    console = Console()
except ImportError:  # graceful fallback
    HAS_RICH = False
    console = None  # type: ignore[assignment]


# ---------------- Utilities ---------------- #

def run_cmd(cmd: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def tty_colour(code: str, text: str) -> str:
    """Basic ANSI colour for non-Rich fallback."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return tty_colour("1", text)


def green(text: str) -> str:
    return tty_colour("32", text)


def yellow(text: str) -> str:
    return tty_colour("33", text)


def red(text: str) -> str:
    return tty_colour("31", text)


def parse_pmset() -> Dict[str, Optional[str]]:
    out = run_cmd(["pmset", "-g", "batt"])
    info: Dict[str, Optional[str]] = {
        "raw": out,
        "source": None,
        "percent": None,
        "status": None,
        "time_remaining": None,
    }
    if not out:
        return info

    lines = out.splitlines()

    # First line: "Now drawing from 'AC Power'"
    if lines:
        m = re.search(r"Now drawing from '([^']+)'", lines[0])
        if m:
            info["source"] = m.group(1)

    # Second line has the battery info
    if len(lines) >= 2:
        line = lines[1]
        # Example: "-InternalBattery-0 (...) 85%; charging; 1:04 remaining present: true"
        m = re.search(r"(\d+)%", line)
        if m:
            info["percent"] = m.group(1)

        m = re.search(r"\d+%\s*;\s*([^;]+);", line)
        if m:
            info["status"] = m.group(1).strip()

        m = re.search(r";\s*([^;]*remaining[^;]*)", line)
        if m:
            info["time_remaining"] = m.group(1).strip()

    return info


def get_sppower_json() -> Optional[Dict[str, Any]]:
    sp = shutil.which("system_profiler") or "/usr/sbin/system_profiler"
    out = run_cmd([sp, "SPPowerDataType", "-json"])
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def boolish_to_str(v: Any) -> str:
    if v is None:
        return "Unknown"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    s = str(v).strip().upper()
    if s in {"TRUE", "YES", "1"}:
        return "Yes"
    if s in {"FALSE", "NO", "0"}:
        return "No"
    return str(v)


def extract_battery_and_charger(
    data: Dict[str, Any],
) -> Dict[str, Optional[Any]]:
    """
    Parse SPPowerDataType JSON into a friendlier dict.

    The JSON looks like:
      { "SPPowerDataType": [ { "_name": "...", "sppower_battery_charge_info": {...}, ... }, ... ] }
    Some entries have battery fields, some have charger fields, etc.
    """
    result: Dict[str, Optional[Any]] = {
        "current_capacity": None,
        "max_capacity": None,
        "fully_charged": None,
        "is_charging": None,
        "cycle_count": None,
        "health": None,
        "battery_serial": None,
        "voltage_mV": None,
        "amperage_mA": None,
        "charger_name": None,
        "charger_watts": None,
        "charger_manufacturer": None,
        "charger_serial": None,
        "charger_connected": None,
        "charger_is_charging": None,
    }

    entries = data.get("SPPowerDataType", [])
    if isinstance(entries, dict):
        entries = [entries]

    battery_entry = None
    charger_entry = None

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        # Battery entry has charge/health/model info
        if "sppower_battery_charge_info" in entry:
            battery_entry = entry

        # Charger entry exposes charger connection fields
        if (
            "sppower_battery_charger_connected" in entry
            or "sppower_ac_charger_watts" in entry
        ):
            charger_entry = entry

    if battery_entry:
        charge = battery_entry.get("sppower_battery_charge_info", {})
        health = battery_entry.get("sppower_battery_health_info", {})
        model = battery_entry.get("sppower_battery_model_info", {})

        result["current_capacity"] = to_int(
            charge.get("sppower_battery_current_capacity")
        )
        result["max_capacity"] = to_int(
            charge.get("sppower_battery_max_capacity")
        )
        result["fully_charged"] = charge.get(
            "sppower_battery_fully_charged"
        )
        result["is_charging"] = charge.get("sppower_battery_is_charging")

        result["cycle_count"] = to_int(
            health.get("sppower_battery_cycle_count")
        )
        result["health"] = health.get("sppower_battery_health")
        result["battery_serial"] = model.get(
            "sppower_battery_serial_number"
        )

        result["voltage_mV"] = to_int(
            battery_entry.get("sppower_current_voltage")
        )
        result["amperage_mA"] = to_int(
            battery_entry.get("sppower_current_amperage")
        )

    if charger_entry:
        result["charger_name"] = charger_entry.get(
            "sppower_ac_charger_name"
        )
        result["charger_manufacturer"] = charger_entry.get(
            "sppower_ac_charger_manufacturer"
        )
        result["charger_serial"] = charger_entry.get(
            "sppower_ac_charger_serial_number"
        )
        result["charger_watts"] = to_int(
            charger_entry.get("sppower_ac_charger_watts")
        )
        result["charger_connected"] = charger_entry.get(
            "sppower_battery_charger_connected"
        )
        result["charger_is_charging"] = charger_entry.get(
            "sppower_battery_is_charging"
        )

    return result


# ---------------- Pretty printing ---------------- #

def rich_percent_cell(percent_str: Optional[str]) -> Any:
    if percent_str is None:
        return "Unknown"

    try:
        p = int(percent_str)
    except ValueError:
        return percent_str + "%"

    if p >= 80:
        style = "bold green"
    elif p >= 40:
        style = "bold yellow"
    else:
        style = "bold red"

    if HAS_RICH:
        return Text(f"{p}%", style=style)
    else:
        if p >= 80:
            return green(f"{p}%")
        elif p >= 40:
            return yellow(f"{p}%")
        else:
            return red(f"{p}%")


def rich_health_cell(health: Optional[str]) -> Any:
    if not health:
        return "Unknown"

    h = health.lower()
    if "normal" in h or "good" in h:
        style = "green"
    elif "soon" in h or "service" in h or "replace" in h:
        style = "bold red"
    else:
        style = "yellow"

    if HAS_RICH:
        return Text(health, style=style)
    else:
        if "normal" in h or "good" in h:
            return green(health)
        elif "soon" in h or "service" in h or "replace" in h:
            return red(health)
        else:
            return yellow(health)


def print_with_rich(pmset_info: Dict[str, Optional[str]], detail: Dict[str, Any]) -> None:
    src = pmset_info.get("source") or "Unknown"
    status = pmset_info.get("status") or "Unknown"
    time_rem = pmset_info.get("time_remaining") or "Unknown"

    console.rule("[bold]🔋 Battery & Power")
    # Summary line
    summary = Text()
    summary.append("🔋 ", style="bold")
    summary.append(str(rich_percent_cell(pmset_info.get("percent"))))
    summary.append(f" • {status}")
    summary.append(f" • Source: {src}")
    summary.append(f" • {time_rem}")
    console.print(summary)
    console.print()

    # Battery table
    batt_table = Table(
        title="Battery",
        box=box.SIMPLE_HEAVY,
        show_header=False,
        expand=False,
    )
    batt_table.add_column("Metric", style="bold cyan")
    batt_table.add_column("Value", style="white")

    batt_table.add_row("Power source", src)
    batt_table.add_row("State", status)
    batt_table.add_row("Charge", rich_percent_cell(pmset_info.get("percent")))
    batt_table.add_row("Time remaining", time_rem)

    health = detail.get("health")
    batt_table.add_row("Health", rich_health_cell(health))

    cycles = detail.get("cycle_count")
    batt_table.add_row("Cycle count", str(cycles) if cycles is not None else "Unknown")

    cur = detail.get("current_capacity")
    maxc = detail.get("max_capacity")
    if cur is not None or maxc is not None:
        cap_str = f"{cur or '?'} / {maxc or '?'} mAh"
    else:
        cap_str = "Unknown"
    batt_table.add_row("Capacity", cap_str)

    volt = detail.get("voltage_mV")
    amp = detail.get("amperage_mA")
    if volt or amp:
        va = []
        if volt:
            va.append(f"{volt} mV")
        if amp:
            va.append(f"{amp} mA")
        batt_table.add_row("Voltage/Amperage", ", ".join(va))

    serial = detail.get("battery_serial")
    if serial:
        batt_table.add_row("Serial", serial)

    console.print(batt_table)
    console.print()

    # Adapter table
    adapter_table = Table(
        title="Adapter",
        box=box.SIMPLE_HEAVY,
        show_header=False,
        expand=False,
    )
    adapter_table.add_column("Metric", style="bold cyan")
    adapter_table.add_column("Value", style="white")

    adapter_table.add_row("Connected", boolish_to_str(detail.get("charger_connected")))
    adapter_table.add_row("Charging", boolish_to_str(detail.get("charger_is_charging")))

    watts = detail.get("charger_watts")
    adapter_table.add_row("Wattage", f"{watts} W" if watts is not None else "Unknown")

    name = detail.get("charger_name")
    if name:
        adapter_table.add_row("Name", name)

    manf = detail.get("charger_manufacturer")
    if manf:
        adapter_table.add_row("Manufacturer", manf)

    cserial = detail.get("charger_serial")
    if cserial:
        adapter_table.add_row("Serial", cserial)

    console.print(adapter_table)

    # Raw pmset panel at the bottom
    raw = pmset_info.get("raw") or "pmset output not available."
    console.print()
    console.print(Panel.fit(raw, title="Raw pmset", box=box.SQUARE))


def print_plain(pmset_info: Dict[str, Optional[str]], detail: Dict[str, Any]) -> None:
    print(bold("Battery & Power"))
    print("─" * 50)
    src = pmset_info.get("source") or "Unknown"
    status = pmset_info.get("status") or "Unknown"
    time_rem = pmset_info.get("time_remaining") or "Unknown"
    pct = rich_percent_cell(pmset_info.get("percent"))

    print(f"Power source     : {src}")
    print(f"State            : {status}")
    print(f"Charge           : {pct}")
    print(f"Time remaining   : {time_rem}")

    print(f"Health           : {rich_health_cell(detail.get('health'))}")
    cycles = detail.get("cycle_count")
    print(f"Cycle count      : {cycles or 'Unknown'}")

    cur = detail.get("current_capacity")
    maxc = detail.get("max_capacity")
    if cur is not None or maxc is not None:
        print(f"Capacity         : {cur or '?'} / {maxc or '?'} mAh")

    volt = detail.get("voltage_mV")
    amp = detail.get("amperage_mA")
    if volt or amp:
        vs = []
        if volt:
            vs.append(f"{volt} mV")
        if amp:
            vs.append(f"{amp} mA")
        print(f"Voltage/Amperage : {', '.join(vs)}")

    serial = detail.get("battery_serial")
    if serial:
        print(f"Battery serial   : {serial}")

    print("\n" + bold("Adapter"))
    print("─" * 50)
    print(f"Connected        : {boolish_to_str(detail.get('charger_connected'))}")
    print(f"Charging         : {boolish_to_str(detail.get('charger_is_charging'))}")
    watts = detail.get("charger_watts")
    print(f"Wattage          : {watts or 'Unknown'}")
    name = detail.get("charger_name")
    if name:
        print(f"Name             : {name}")
    manf = detail.get("charger_manufacturer")
    if manf:
        print(f"Manufacturer     : {manf}")
    cserial = detail.get("charger_serial")
    if cserial:
        print(f"Serial           : {cserial}")

    print("\n" + bold("Raw pmset"))
    print("─" * 50)
    raw = pmset_info.get("raw") or "pmset output not available."
    print(raw)


def main() -> None:
    if platform.system() != "Darwin":
        print("This script is intended to run on macOS.")
        sys.exit(1)

    pmset_info = parse_pmset()
    sp = get_sppower_json()
    detail = extract_battery_and_charger(sp) if sp else {}

    if HAS_RICH:
        print_with_rich(pmset_info, detail)
    else:
        print_plain(pmset_info, detail)


if __name__ == "__main__":
    main()
