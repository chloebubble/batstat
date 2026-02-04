#!/usr/bin/env python3
"""
Pretty battery / charger overview for macOS and USB-connected iOS devices.

- Uses `pmset -g batt` for live status.
- Uses `system_profiler SPPowerDataType -json` for health + charger info.
- Optional: `rich` for nice colours/tables (recommended).
- Optional: `libimobiledevice` (`ideviceinfo`) for iOS battery stats.

Tested layout on macOS; key names are based on SPPowerDataType JSON schema.
"""

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

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


def run_cmd_capture(cmd: List[str]) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        return stdout, stderr, result.returncode
    except OSError as exc:
        return None, str(exc), None


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


def to_int_signed_64(v: Any) -> Optional[int]:
    """Convert to signed 64-bit int when ioreg exposes unsigned wraparound."""
    val = to_int(v)
    if val is None:
        return None
    if val >= 2**63:
        return val - 2**64
    return val


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
        "design_capacity": None,
        "fully_charged": None,
        "is_charging": None,
        "cycle_count": None,
        "health": None,
        "health_pct": None,
        "battery_serial": None,
        "voltage_mV": None,
        "amperage_mA": None,
        "temperature_c": None,
        "manufacture_date": None,
        "charging_watts": None,
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


def _parse_ioreg_value(raw: str) -> Any:
    """Convert an ioreg value string into Python types."""
    raw = raw.strip()
    if raw in {"Yes", "No"}:
        return raw == "Yes"
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def parse_ioreg_battery() -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Parse `ioreg -rd1 -c AppleSmartBattery` output.

    Returns (flat_dict, raw_text). The flat dict only contains top-level key/value
    pairs plus a few parsed fields extracted with regex from nested dict lines.
    """
    out = run_cmd(["ioreg", "-rd1", "-c", "AppleSmartBattery"])
    if not out:
        return {}, None

    kv_re = re.compile(r'"([^"]+)"\s*=\s*(.+)')
    flat: Dict[str, Any] = {}

    # Extract nested values we care about (AdapterDetails watts, ManufactureDate)
    adapter_watts_match = re.search(
        r'"(?:AppleRawAdapterDetails|AdapterDetails)"[^\n]*"Watts"=([0-9]+)', out
    )
    if adapter_watts_match:
        flat["AdapterWatts"] = to_int(adapter_watts_match.group(1))
    manuf_match = re.search(r'ManufactureDate"=([0-9]+)', out)
    if manuf_match:
        flat["ManufactureDateRaw"] = manuf_match.group(1)

    for line in out.splitlines():
        m = kv_re.match(line.strip())
        if not m:
            continue
        key, raw_val = m.groups()
        flat[key] = _parse_ioreg_value(raw_val)

    return flat, out


def _decode_manufacture_date(raw: str) -> Optional[str]:
    """
    Attempt to decode battery manufacture date.

    Some batteries expose the date as a 6-byte ASCII integer stored little-endian.
    If we can turn it into a plausible YYYY-MM-DD, return that string.
    """
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return None

    # Build bytes big-endian, then check if all digits.
    byte_len = max(1, (val.bit_length() + 7) // 8)
    try:
        b = val.to_bytes(byte_len, "big")
    except OverflowError:
        return None
    if not all(48 <= x <= 57 for x in b):
        return None

    s = b.decode()
    candidates = []
    if len(s) == 6:  # typical "YYMMDD" or reversed
        candidates.append(s)
        candidates.append(s[::-1])

    for cand in candidates:
        if len(cand) != 6:
            continue
        yy = int(cand[:2])
        mm = int(cand[2:4])
        dd = int(cand[4:])
        # Treat yy as 2000-2099
        year = 2000 + yy
        try:
            import datetime

            if not (2000 <= year <= datetime.date.today().year):
                continue
            dt = datetime.date(year, mm, dd)
            return dt.isoformat()
        except ValueError:
            continue
    return None


def enrich_with_ioreg(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in missing metrics using AppleSmartBattery (ioreg)."""
    io_dict, raw = parse_ioreg_battery()
    if not io_dict:
        return detail

    def set_if_absent(key: str, value: Any) -> None:
        if value is None:
            return
        if detail.get(key) is None:
            detail[key] = value
        else:
            detail[key] = value

    design = to_int(io_dict.get("DesignCapacity"))
    max_cap = to_int(io_dict.get("AppleRawMaxCapacity") or io_dict.get("MaxCapacity"))
    cur_cap = to_int(
        io_dict.get("AppleRawCurrentCapacity") or io_dict.get("CurrentCapacity")
    )

    set_if_absent("design_capacity", design)
    set_if_absent("max_capacity", max_cap)
    set_if_absent("current_capacity", cur_cap)

    cycles = to_int(io_dict.get("CycleCount"))
    set_if_absent("cycle_count", cycles)

    voltage = to_int(io_dict.get("Voltage") or io_dict.get("AppleRawBatteryVoltage"))
    amperage = to_int_signed_64(
        io_dict.get("Amperage") or io_dict.get("InstantAmperage")
    )
    set_if_absent("voltage_mV", voltage)
    set_if_absent("amperage_mA", amperage)

    set_if_absent("charger_is_charging", io_dict.get("IsCharging"))
    set_if_absent("charger_connected", io_dict.get("ExternalConnected"))

    # Real-time charging power (approx). Only show when charging/connected.
    if (
        voltage is not None
        and amperage is not None
        and amperage > 0
        and (detail.get("charger_is_charging") or detail.get("charger_connected"))
    ):
        watts = round(voltage * amperage / 1_000_000, 1)
        set_if_absent("charging_watts", watts)

    temp_raw = io_dict.get("Temperature") or io_dict.get("VirtualTemperature")
    if isinstance(temp_raw, (int, float)):
        # Smart battery spec: temperature in 0.1 Kelvin.
        temp_c = round((temp_raw / 10) - 273.15, 1)
        set_if_absent("temperature_c", temp_c)

    # Rated charger wattage if present.
    set_if_absent("charger_watts", to_int(io_dict.get("AdapterWatts")))

    if max_cap and design:
        health_pct = round(max_cap / design * 100, 1)
        set_if_absent("health_pct", health_pct)

    manuf_raw = io_dict.get("ManufactureDateRaw")
    manuf_date = _decode_manufacture_date(manuf_raw) if manuf_raw else None
    if manuf_date:
        set_if_absent("manufacture_date", manuf_date)

    return detail


def _parse_ideviceinfo_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if raw in {"Yes", "No"}:
        return raw == "Yes"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def parse_ideviceinfo_kv(out: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        data[key.strip()] = _parse_ideviceinfo_value(raw)
    return data


def list_ios_devices() -> List[str]:
    idevice_id = shutil.which("idevice_id")
    if not idevice_id:
        return []
    out = run_cmd([idevice_id, "-l"])
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def get_ios_device_name(udid: Optional[str]) -> Optional[str]:
    ideviceinfo = shutil.which("ideviceinfo")
    if not ideviceinfo:
        return None
    cmd = [ideviceinfo, "-k", "DeviceName"]
    if udid:
        cmd[1:1] = ["-u", udid]
    out = run_cmd(cmd)
    if not out:
        return None
    if ":" in out:
        _, value = out.split(":", 1)
        return value.strip() or None
    return out.strip()


def get_ios_battery_info(
    udid: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    ideviceinfo = shutil.which("ideviceinfo")
    if not ideviceinfo:
        return None, None, "ideviceinfo not found. Install libimobiledevice."
    cmd = [ideviceinfo, "-q", "com.apple.mobile.battery"]
    if udid:
        cmd[1:1] = ["-u", udid]
    out, err, code = run_cmd_capture(cmd)
    if out is None:
        return None, None, err or "Failed to run ideviceinfo."
    if code != 0 or not out:
        msg = err or "No battery data returned from iOS device."
        return None, out, msg
    return parse_ideviceinfo_kv(out), out, None


def _first_present(data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _first_int(data: Dict[str, Any], keys: List[str]) -> Optional[int]:
    val = _first_present(data, keys)
    return to_int(val)


def _to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return value == 1
        return None
    s = str(value).strip().lower()
    if s in {"true", "yes", "1"}:
        return True
    if s in {"false", "no", "0"}:
        return False
    return None


def _minutes_to_hhmm(minutes: int) -> Optional[str]:
    if minutes < 0:
        return None
    hours, mins = divmod(minutes, 60)
    return f"{hours}:{mins:02d}"


def build_ios_views(
    data: Dict[str, Any],
    device_name: Optional[str],
    device_udid: Optional[str],
    raw: Optional[str],
) -> Tuple[Dict[str, Optional[str]], Dict[str, Any]]:
    percent = _first_int(
        data,
        [
            "BatteryCurrentCapacity",
            "BatteryPercent",
            "BatteryLevel",
            "CurrentCapacityPercent",
        ],
    )
    is_charging = _to_bool(
        _first_present(
            data,
            [
                "BatteryIsCharging",
                "IsCharging",
                "Charging",
            ],
        )
    )
    fully_charged = _to_bool(
        _first_present(
            data,
            [
                "BatteryIsFullyCharged",
                "FullyCharged",
            ],
        )
    )
    external_connected = _to_bool(
        _first_present(
            data,
            [
                "ExternalConnected",
                "ExternalPowerConnected",
            ],
        )
    )

    status = "Unknown"
    if fully_charged is True:
        status = "fully charged"
    elif is_charging is True:
        status = "charging"
    elif is_charging is False:
        status = "discharging"
    elif external_connected is True:
        status = "connected"

    time_remaining = None
    time_to_full = _first_int(data, ["BatteryTimeToFull", "TimeToFull"])
    time_to_empty = _first_int(data, ["BatteryTimeToEmpty", "TimeToEmpty"])
    if time_to_full is not None and is_charging is True:
        hhmm = _minutes_to_hhmm(time_to_full)
        if hhmm:
            time_remaining = f"{hhmm} until full"
    elif time_to_empty is not None:
        hhmm = _minutes_to_hhmm(time_to_empty)
        if hhmm:
            time_remaining = f"{hhmm} remaining"

    pmset_info: Dict[str, Optional[str]] = {
        "raw": raw,
        "source": "USB (iOS)",
        "percent": str(percent) if percent is not None else None,
        "status": status,
        "time_remaining": time_remaining,
    }

    detail: Dict[str, Any] = {
        "device_type": "ios",
        "device_name": device_name,
        "device_udid": device_udid,
        "current_capacity": _first_int(data, ["CurrentCapacity", "BatteryCurrentCapacityRaw"]),
        "max_capacity": _first_int(
            data,
            [
                "NominalChargeCapacity",
                "BatteryCapacity",
                "MaxCapacity",
                "FullChargeCapacity",
            ],
        ),
        "design_capacity": _first_int(data, ["DesignCapacity"]),
        "fully_charged": fully_charged,
        "is_charging": is_charging,
        "cycle_count": _first_int(data, ["CycleCount", "BatteryCycleCount"]),
        "health": _first_present(data, ["BatteryHealth", "BatteryHealthStatus"]),
        "battery_serial": _first_present(data, ["Serial", "BatterySerial", "BatterySerialNumber"]),
        "voltage_mV": _first_int(data, ["BatteryVoltage", "Voltage"]),
        "amperage_mA": _first_int(data, ["Amperage", "InstantAmperage", "BatteryAmperage"]),
        "temperature_c": None,
        "temperature_raw": _first_present(data, ["BatteryTemperature", "Temperature"]),
        "manufacture_date": _first_present(data, ["ManufactureDate", "ManufactureDateRaw"]),
        "charging_watts": None,
        "charger_name": None,
        "charger_watts": None,
        "charger_manufacturer": None,
        "charger_serial": None,
        "charger_connected": external_connected,
        "charger_is_charging": is_charging,
    }

    if detail.get("max_capacity") and detail.get("design_capacity"):
        max_cap = detail["max_capacity"]
        design = detail["design_capacity"]
        if isinstance(max_cap, int) and isinstance(design, int) and design > 0:
            detail["health_pct"] = round(max_cap / design * 100, 1)

    return pmset_info, detail


# ---------------- Pretty printing ---------------- #

def is_ios_detail(detail: Dict[str, Any]) -> bool:
    return detail.get("device_type") == "ios"


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


def print_with_rich(
    pmset_info: Dict[str, Optional[str]],
    detail: Dict[str, Any],
    show_raw: bool,
) -> None:
    src = pmset_info.get("source") or "Unknown"
    status = pmset_info.get("status") or "Unknown"
    time_rem = pmset_info.get("time_remaining") or "Unknown"

    header = "iOS Battery" if is_ios_detail(detail) else "Battery & Power"
    power_label = "Connection" if is_ios_detail(detail) else "Power source"
    adapter_title = "Power" if is_ios_detail(detail) else "Adapter"

    console.rule(f"[bold]🔋 {header}")
    # Summary line
    summary = Text()
    summary.append("🔋 ", style="bold")
    summary.append(str(rich_percent_cell(pmset_info.get("percent"))))
    summary.append(f" • {status}")
    summary_label = "Connection" if is_ios_detail(detail) else "Source"
    summary.append(f" • {summary_label}: {src}")
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

    device_name = detail.get("device_name")
    if device_name:
        batt_table.add_row("Device", str(device_name))
    device_udid = detail.get("device_udid")
    if device_udid:
        batt_table.add_row("UDID", str(device_udid))

    batt_table.add_row(power_label, src)
    batt_table.add_row("State", status)
    batt_table.add_row("Charge", rich_percent_cell(pmset_info.get("percent")))
    batt_table.add_row("Time remaining", time_rem)

    health = detail.get("health")
    health_pct = detail.get("health_pct")
    health_label = health or "Unknown"
    if health_pct:
        health_label = f"{health_label} ({health_pct}%)" if health else f"{health_pct}%"
    batt_table.add_row("Health", rich_health_cell(health_label))

    cycles = detail.get("cycle_count")
    batt_table.add_row("Cycle count", str(cycles) if cycles is not None else "Unknown")

    cur = detail.get("current_capacity")
    maxc = detail.get("max_capacity")
    design = detail.get("design_capacity")
    if cur is not None:
        batt_table.add_row("Charge (mAh)", f"{cur} mAh")
    if maxc is not None:
        batt_table.add_row("Full charge cap", f"{maxc} mAh")
    if design is not None:
        batt_table.add_row("Design capacity", f"{design} mAh")

    volt = detail.get("voltage_mV")
    amp = detail.get("amperage_mA")
    if volt or amp:
        va = []
        if volt:
            va.append(f"{volt} mV")
        if amp:
            va.append(f"{amp} mA")
        batt_table.add_row("Voltage/Amperage", ", ".join(va))

    temp_c = detail.get("temperature_c")
    if temp_c is not None:
        batt_table.add_row("Temperature", f"{temp_c} °C")
    elif detail.get("temperature_raw") is not None:
        batt_table.add_row("Temperature (raw)", str(detail.get("temperature_raw")))

    manuf = detail.get("manufacture_date")
    if manuf:
        batt_table.add_row("Manufactured", manuf)

    serial = detail.get("battery_serial")
    if serial:
        batt_table.add_row("Serial", serial)

    console.print(batt_table)
    console.print()

    # Adapter table
    adapter_table = Table(
        title=adapter_title,
        box=box.SIMPLE_HEAVY,
        show_header=False,
        expand=False,
    )
    adapter_table.add_column("Metric", style="bold cyan")
    adapter_table.add_column("Value", style="white")

    adapter_table.add_row("Connected", boolish_to_str(detail.get("charger_connected")))
    adapter_table.add_row("Charging", boolish_to_str(detail.get("charger_is_charging")))

    watts_rated = detail.get("charger_watts")
    adapter_table.add_row(
        "Adapter watts", f"{watts_rated} W" if watts_rated is not None else "N/A"
    )

    watts_live = detail.get("charging_watts")
    adapter_table.add_row(
        "Charging power", f"{watts_live} W" if watts_live is not None else "N/A"
    )

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

    if show_raw:
        # Raw output panel at the bottom
        raw = pmset_info.get("raw") or "Raw output not available."
        console.print()
        console.print(Panel.fit(raw, title="Raw output", box=box.SQUARE))


def print_plain(
    pmset_info: Dict[str, Optional[str]],
    detail: Dict[str, Any],
    show_raw: bool,
) -> None:
    header = "iOS Battery" if is_ios_detail(detail) else "Battery & Power"
    power_label = "Connection" if is_ios_detail(detail) else "Power source"
    adapter_title = "Power" if is_ios_detail(detail) else "Adapter"

    print(bold(header))
    print("─" * 50)
    src = pmset_info.get("source") or "Unknown"
    status = pmset_info.get("status") or "Unknown"
    time_rem = pmset_info.get("time_remaining") or "Unknown"
    pct = rich_percent_cell(pmset_info.get("percent"))

    device_name = detail.get("device_name")
    if device_name:
        print(f"Device           : {device_name}")
    device_udid = detail.get("device_udid")
    if device_udid:
        print(f"UDID             : {device_udid}")

    print(f"{power_label:16}: {src}")
    print(f"State            : {status}")
    print(f"Charge           : {pct}")
    print(f"Time remaining   : {time_rem}")

    health = detail.get("health")
    health_pct = detail.get("health_pct")
    health_label = health or "Unknown"
    if health_pct:
        health_label = f"{health_label} ({health_pct}%)" if health else f"{health_pct}%"
    print(f"Health           : {rich_health_cell(health_label)}")
    cycles = detail.get("cycle_count")
    print(f"Cycle count      : {cycles or 'Unknown'}")

    cur = detail.get("current_capacity")
    maxc = detail.get("max_capacity")
    design = detail.get("design_capacity")
    if cur is not None:
        print(f"Charge (mAh)     : {cur} mAh")
    if maxc is not None:
        print(f"Full charge cap  : {maxc} mAh")
    if design is not None:
        print(f"Design capacity  : {design} mAh")

    volt = detail.get("voltage_mV")
    amp = detail.get("amperage_mA")
    if volt or amp:
        vs = []
        if volt:
            vs.append(f"{volt} mV")
        if amp:
            vs.append(f"{amp} mA")
        print(f"Voltage/Amperage : {', '.join(vs)}")

    temp_c = detail.get("temperature_c")
    if temp_c is not None:
        print(f"Temperature      : {temp_c} °C")
    elif detail.get("temperature_raw") is not None:
        print(f"Temperature (raw): {detail.get('temperature_raw')}")

    manuf = detail.get("manufacture_date")
    if manuf:
        print(f"Manufactured     : {manuf}")

    serial = detail.get("battery_serial")
    if serial:
        print(f"Battery serial   : {serial}")

    print("\n" + bold(adapter_title))
    print("─" * 50)
    print(f"Connected        : {boolish_to_str(detail.get('charger_connected'))}")
    print(f"Charging         : {boolish_to_str(detail.get('charger_is_charging'))}")
    watts_rated = detail.get("charger_watts")
    print(f"Adapter watts    : {watts_rated} W" if watts_rated is not None else "Adapter watts    : N/A")
    watts_live = detail.get("charging_watts")
    if watts_live is not None:
        print(f"Charging power   : {watts_live} W")
    else:
        print("Charging power   : N/A")
    name = detail.get("charger_name")
    if name:
        print(f"Name             : {name}")
    manf = detail.get("charger_manufacturer")
    if manf:
        print(f"Manufacturer     : {manf}")
    cserial = detail.get("charger_serial")
    if cserial:
        print(f"Serial           : {cserial}")

    if show_raw:
        print("\n" + bold("Raw output"))
        print("─" * 50)
        raw = pmset_info.get("raw") or "Raw output not available."
        print(raw)


def render_output(
    pmset_info: Dict[str, Optional[str]],
    detail: Dict[str, Any],
    show_raw: bool,
) -> None:
    if HAS_RICH:
        print_with_rich(pmset_info, detail, show_raw)
    else:
        print_plain(pmset_info, detail, show_raw)


def main() -> None:
    if platform.system() != "Darwin":
        print("This script is intended to run on macOS.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Pretty battery / charger overview for macOS and USB-connected iOS devices."
    )
    parser.add_argument(
        "-r",
        "--raw",
        action="store_true",
        help="Show raw output for the selected data source.",
    )
    parser.add_argument(
        "--ios",
        action="store_true",
        help="Read battery info from a USB-connected iOS device (requires libimobiledevice).",
    )
    parser.add_argument(
        "--no-ios",
        action="store_true",
        help="Disable auto-detection of USB-connected iOS devices.",
    )
    parser.add_argument(
        "--ios-udid",
        help="Target a specific iOS device by UDID (useful when multiple are connected).",
    )
    args = parser.parse_args()

    if args.ios:
        udid = args.ios_udid
        devices = list_ios_devices()
        if udid is None and len(devices) > 1:
            print("Multiple iOS devices detected. Use --ios-udid to select one:")
            for dev in devices:
                print(f"  {dev}")
            sys.exit(2)
        if udid is None and len(devices) == 1:
            udid = devices[0]

        data, raw, err = get_ios_battery_info(udid)
        if err or data is None:
            print(err or "Unable to read iOS battery info.")
            print("Ensure the device is connected, unlocked, trusted, and paired.")
            sys.exit(1)

        device_name = get_ios_device_name(udid)
        pmset_info, detail = build_ios_views(data, device_name, udid, raw)

        render_output(pmset_info, detail, args.raw)
        return

    pmset_info = parse_pmset()
    sp = get_sppower_json()
    detail = extract_battery_and_charger(sp) if sp else {}
    detail = enrich_with_ioreg(detail)

    render_output(pmset_info, detail, args.raw)

    if args.no_ios:
        return

    devices = list_ios_devices()
    if not devices:
        return

    for udid in devices:
        data, raw, err = get_ios_battery_info(udid)
        if err or data is None:
            print(
                f"Warning: unable to read iOS battery info for {udid}: {err or 'unknown error'}",
                file=sys.stderr,
            )
            continue
        device_name = get_ios_device_name(udid)
        pmset_info, detail = build_ios_views(data, device_name, udid, raw)
        print()
        render_output(pmset_info, detail, args.raw)


if __name__ == "__main__":
    main()
