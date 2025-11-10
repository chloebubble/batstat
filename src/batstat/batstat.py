#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["psutil>=7.1.3"]
# ///
"""
Battery Status Script - batstat
A beautiful battery status display for macOS using ioreg
Refactored from fish shell to Python for better maintainability and functionality
"""

import subprocess
import re
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    ORANGE = '\033[38;5;208m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[38;5;246m'

    @classmethod
    def disable_colors(cls):
        """Disable all colors for non-interactive terminals"""
        cls.GREEN = cls.YELLOW = cls.ORANGE = cls.RED = cls.BLUE = ''
        cls.PURPLE = cls.CYAN = cls.GRAY = cls.RESET = ''


class BatteryData:
    """Container for battery information"""

    def __init__(self, ioreg_output: str):
        self.data = self._parse_ioreg(ioreg_output)

    def _parse_ioreg(self, output: str) -> Dict[str, str]:
        """Parse ioreg output and extract battery metrics"""
        data = {}

        # Define patterns for each metric
        patterns = {
            'current_capacity': r'"CurrentCapacity" = (\d+)',
            'max_capacity': r'"MaxCapacity" = (\d+)',
            'design_capacity': r'"DesignCapacity" = (\d+)',
            'cycle_count': r'"CycleCount" = (\d+)',
            'temperature': r'"Temperature" = (\d+)',
            'voltage': r'"Voltage" = (\d+)',
            'amperage': r'"Amperage" = (-?\d+)',
            'is_charging': r'"IsCharging" = (\w+)',
            'external_connected': r'"ExternalConnected" = (\w+)',
            'fully_charged': r'"FullyCharged" = (\w+)',
            'time_remaining': r'"TimeRemaining" = (-?\d+)',
            'serial': r'"Serial" = "([A-Za-z0-9]*)"',
            'adapter_name': r'"Name" = "([A-Za-z0-9 -]*)"',
            'adapter_watts': r'"Watts" = (\d+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            data[key] = match.group(1) if match else None

        return data

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer value from data"""
        value = self.data.get(key)
        return int(value) if value and value.isdigit() else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float value from data"""
        value = self.data.get(key)
        return float(value) if value else default

    def get_str(self, key: str, default: str = "") -> str:
        """Get string value from data"""
        return self.data.get(key) or default


def get_charger_info() -> Dict[str, str]:
    """Get charger information from system_profiler"""
    charger_data = {}

    try:
        result = subprocess.run(
            ['system_profiler', 'SPPowerDataType'],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout

        # Parse AC Charger Information
        if 'AC Charger Information:' in output:
            # Extract charger wattage
            wattage_match = re.search(r'Wattage \(W\): (\d+)', output)
            if wattage_match:
                charger_data['charger_wattage'] = wattage_match.group(1)

            # Extract charger name from AC Charger section
            charger_name_match = re.search(r'AC Charger Information:[\s\S]*?Name: (.+)', output)
            if charger_name_match:
                charger_data['charger_name'] = charger_name_match.group(1).strip()

            # Extract charger connected status
            connected_match = re.search(r'Connected: (\w+)', output)
            if connected_match:
                charger_data['charger_connected'] = connected_match.group(1)

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return charger_data


def get_battery_data() -> Optional[BatteryData]:
    """Get battery data from ioreg"""
    try:
        result = subprocess.run(
            ['ioreg', '-lrn', 'AppleSmartBattery'],
            capture_output=True,
            text=True,
            check=True
        )
        return BatteryData(result.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def calculate_battery_percentage(battery: BatteryData) -> float:
    """Calculate battery percentage"""
    current = battery.get_int('current_capacity')
    max_cap = battery.get_int('max_capacity')

    if max_cap == 0:
        return 0.0
    return round(current * 100.0 / max_cap, 1)


def calculate_health_percentage(battery: BatteryData) -> float:
    """Calculate battery health percentage"""
    max_cap = battery.get_int('max_capacity')
    design_cap = battery.get_int('design_capacity')

    if design_cap == 0:
        return 0.0
    return round(max_cap * 100.0 / design_cap, 1)


def get_battery_status(battery: BatteryData) -> Tuple[str, str]:
    """Determine battery status and icon"""
    is_charging = battery.get_str('is_charging') == "Yes"
    external_connected = battery.get_str('external_connected') == "Yes"
    fully_charged = battery.get_str('fully_charged') == "Yes"

    if is_charging:
        return "⚡", "Charging"
    elif external_connected and fully_charged:
        return "🔌", "Fully Charged"
    elif external_connected:
        return "🔌", "Not Charging"
    else:
        return "🔋", "Discharging"


def format_time_remaining(battery: BatteryData) -> str:
    """Format time remaining string"""
    time_remaining = battery.get_int('time_remaining')
    is_charging = battery.get_str('is_charging') == "Yes"

    if time_remaining in (65535, -1, 0) or time_remaining == 0:
        return "Calculating..." if not is_charging else "Almost full"

    if time_remaining > 0:
        hours = time_remaining // 60
        minutes = time_remaining % 60
        return f"{hours}h {minutes}m"

    return "Almost full"


def get_battery_color(percentage: float) -> str:
    """Get color based on battery percentage"""
    if percentage <= 20:
        return Colors.RED
    elif percentage <= 40:
        return Colors.ORANGE
    elif percentage <= 60:
        return Colors.YELLOW
    else:
        return Colors.GREEN


def get_health_color(health_percentage: float) -> str:
    """Get color based on battery health"""
    if health_percentage <= 60:
        return Colors.RED
    elif health_percentage <= 80:
        return Colors.YELLOW
    else:
        return Colors.GREEN


def create_progress_bar(percentage: float, length: int = 44) -> str:
    """Create a progress bar"""
    filled_length = int(percentage * length / 100)
    empty_length = length - filled_length

    return "█" * filled_length + "░" * empty_length


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def center_text(text: str, width: int) -> str:
    """Center text within given width, properly handling ANSI codes"""
    # Get the visible text length without ANSI codes
    visible_text = strip_ansi_codes(text)
    text_len = len(visible_text)

    if text_len >= width:
        return text[:width]

    padding = width - text_len
    left_pad = padding // 2
    right_pad = padding - left_pad

    return " " * left_pad + text + " " * right_pad



def format_current_draw(amperage: int) -> Tuple[str, str]:
    """Format current draw information"""
    if amperage == 0:
        return "0mA (idle)", Colors.GRAY
    elif amperage > 0:
        return f"+{amperage}mA (charging)", Colors.GREEN
    else:
        return f"{abs(amperage)}mA (drawing)", Colors.ORANGE


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def pad_visible(text: str, width: int) -> str:
    """Pad text with spaces accounting for ANSI escape codes"""
    visible_len = len(strip_ansi_codes(text))
    if visible_len >= width:
        return text
    return text + " " * (width - visible_len)


class AsciiRenderer:
    """Utility for rendering consistently aligned ASCII boxes"""

    def __init__(self, inner_width: int = 44):
        self.inner_width = inner_width
        self.lines: List[str] = []

    def horizontal_rule(self, color: Optional[str] = None, char: str = "─") -> None:
        border = color if color is not None else Colors.GRAY
        self.lines.append(f"{border}+{char * self.inner_width}+{Colors.RESET}")

    def framed_line(self, content: str, border_color: Optional[str] = None) -> None:
        border = border_color if border_color is not None else Colors.GRAY
        padded = pad_visible(content, self.inner_width)
        self.lines.append(f"{border}|{padded}{border}|{Colors.RESET}")

    def blank_line(self) -> None:
        self.lines.append("")

    def banner(self, title: str) -> None:
        self.horizontal_rule(Colors.CYAN)
        banner_text = center_text(
            f"{Colors.PURPLE}🔋 {title} 🔋{Colors.CYAN}",
            self.inner_width
        )
        self.framed_line(banner_text, Colors.CYAN)
        self.horizontal_rule(Colors.CYAN)
        self.blank_line()

    def section(self, title: str, rows: List[str], accent: Optional[str] = None) -> None:
        accent_color = accent if accent is not None else Colors.GRAY
        self.horizontal_rule(accent_color)
        self.framed_line(f" {title}", accent_color)
        self.horizontal_rule(accent_color)
        for row in rows:
            self.framed_line(row)
        self.horizontal_rule()
        self.blank_line()

    def render(self) -> None:
        for line in self.lines:
            print(line)


def format_kv(label: str, value: str, label_width: int = 10) -> str:
    """Format label/value pairs to keep alignment consistent"""
    label_text = f"{label:<{label_width}}"
    return f" {label_text}: {value}"


def display_simple_battery_info(battery: BatteryData) -> None:
    """Display simple battery information for script-friendly output"""
    percentage = calculate_battery_percentage(battery)
    health_percentage = calculate_health_percentage(battery)
    status_icon, status_text = get_battery_status(battery)
    time_str = format_time_remaining(battery)

    temp_celsius = battery.get_float('temperature') / 100.0
    voltage_volts = battery.get_float('voltage') / 1000.0
    cycles = battery.get_int('cycle_count')

    print(f"{percentage:.1f}%")
    print(f"{status_text}")
    print(f"{health_percentage:.1f}%")
    print(f"{cycles}")
    print(f"{temp_celsius:.1f}°C")
    print(f"{voltage_volts:.2f}V")
    print(f"{time_str}")
    print(f"{status_icon}")


def display_battery_status(verbose: bool = True, json_output: bool = False) -> None:
    """Main function to display battery status"""
    battery = get_battery_data()
    if not battery:
        print(f"{Colors.RED}❌ Unable to read battery information{Colors.RESET}")
        sys.exit(1)

    # Get charger information
    charger_info = get_charger_info()

    if json_output:
        import json
        data = {
            "percentage": calculate_battery_percentage(battery),
            "health": calculate_health_percentage(battery),
            "status": get_battery_status(battery)[1],
            "icon": get_battery_status(battery)[0],
            "cycles": battery.get_int('cycle_count'),
            "temperature_celsius": battery.get_float('temperature') / 100.0,
            "temperature_fahrenheit": (battery.get_float('temperature') / 100.0) * 9.0 / 5.0 + 32.0,
            "voltage": battery.get_float('voltage') / 1000.0,
            "amperage": battery.get_int('amperage'),
            "time_remaining": format_time_remaining(battery),
            "serial": battery.get_str('serial'),
            "adapter_name": battery.get_str('adapter_name'),
            "adapter_watts": battery.get_int('adapter_watts'),
            "charger_name": charger_info.get('charger_name', ''),
            "charger_wattage": int(charger_info.get('charger_wattage', 0)) if charger_info.get('charger_wattage') else 0,
            "is_charging": battery.get_str('is_charging') == "Yes",
            "external_connected": battery.get_str('external_connected') == "Yes",
            "fully_charged": battery.get_str('fully_charged') == "Yes",
            "updated_at": datetime.now().isoformat()
        }
        print(json.dumps(data, indent=2))
        return

    if not verbose:
        display_simple_battery_info(battery)
        return

    # Calculate values
    percentage = calculate_battery_percentage(battery)
    health_percentage = calculate_health_percentage(battery)
    status_icon, status_text = get_battery_status(battery)
    time_str = format_time_remaining(battery)

    temp_celsius = battery.get_float('temperature') / 100.0
    temp_fahrenheit = temp_celsius * 9.0 / 5.0 + 32.0
    voltage_volts = battery.get_float('voltage') / 1000.0
    amperage = battery.get_int('amperage')
    current_text, current_color = format_current_draw(amperage)

    battery_color = get_battery_color(percentage)
    health_color = get_health_color(health_percentage)

    renderer = AsciiRenderer(inner_width=44)
    renderer.banner("BATTERY STATUS")

    status_value = f"{status_text:<10} {percentage:>3.0f}% {status_icon}"
    renderer.section(
        "Battery Level",
        [
            format_kv("Status", f"{battery_color}{status_value}{Colors.RESET}"),
            "",
            f"{battery_color}{create_progress_bar(percentage, renderer.inner_width)}{Colors.RESET}"
        ],
        accent=Colors.GRAY
    )

    max_cap = battery.get_int('max_capacity')
    design_cap = battery.get_int('design_capacity')
    cycles = battery.get_int('cycle_count')

    renderer.section(
        "Battery Health",
        [
            format_kv(
                "Health",
                f"{health_color}{health_percentage:>3.0f}%{Colors.RESET} ({max_cap} / {design_cap} mAh)"
            ),
            format_kv("Cycles", f"{Colors.BLUE}{cycles}{Colors.RESET}")
        ],
        accent=Colors.CYAN
    )

    renderer.section(
        "Power Details",
        [
            format_kv("Voltage", f"{Colors.YELLOW}{voltage_volts:>6.2f}V{Colors.RESET}"),
            format_kv("Current", f"{current_color}{current_text}{Colors.RESET}"),
            format_kv(
                "Temp",
                f"{Colors.CYAN}{temp_celsius:.1f}°C{Colors.RESET} / {temp_fahrenheit:.1f}°F"
            )
        ],
        accent=Colors.PURPLE
    )

    if time_str not in ("Calculating...", "Almost full"):
        renderer.section(
            "Time Remaining",
            [format_kv("Estimate", f"{Colors.GREEN}{time_str}{Colors.RESET}")],
            accent=Colors.GREEN
        )

    external_connected = battery.get_str('external_connected') == "Yes"
    charger_name = charger_info.get('charger_name') or battery.get_str('adapter_name')
    charger_wattage = charger_info.get('charger_wattage')

    value_limit = renderer.inner_width - 13  # width minus label + padding

    if external_connected and charger_name:
        adapter_display = truncate_text(charger_name, value_limit)
        watts_value = None
        if charger_wattage:
            watts_value = f"{charger_wattage}W"
        else:
            adapter_watts = battery.get_int('adapter_watts')
            if adapter_watts > 0:
                watts_value = f"{adapter_watts}W"

        adapter_rows = [
            format_kv("Type", f"{Colors.BLUE}{adapter_display}{Colors.RESET}")
        ]

        if watts_value:
            adapter_rows.append(
                format_kv("Power", f"{Colors.YELLOW}{watts_value}{Colors.RESET}")
            )

        renderer.section("Power Adapter", adapter_rows, accent=Colors.BLUE)

    serial = battery.get_str('serial')
    serial_display = truncate_text(serial, value_limit)
    updated_at = datetime.now().strftime("%H:%M:%S")

    renderer.section(
        "System Info",
        [
            format_kv("Serial", serial_display),
            format_kv("Updated", updated_at)
        ]
    )

    print()
    renderer.render()
    print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="A beautiful battery status display for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  batstat              # Show full battery status
  batstat -s           # Show simple output
  batstat -j           # Output JSON format
  batstat --no-color   # Disable colors
        """
    )

    parser.add_argument(
        '-s', '--simple',
        action='store_true',
        help='Show simple, script-friendly output'
    )

    parser.add_argument(
        '-j', '--json',
        action='store_true',
        help='Output in JSON format'
    )

    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )

    args = parser.parse_args()

    # Disable colors if requested or if not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable_colors()

    try:
        display_battery_status(
            verbose=not args.simple,
            json_output=args.json
        )
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
