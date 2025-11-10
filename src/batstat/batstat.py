#!/usr/bin/env python3
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
from typing import Dict, Optional, Tuple


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


def create_header_line(title: str, width: int) -> str:
    """Create a header line with title"""
    base = f"─ {title} "
    base_len = len(base)

    if base_len >= width:
        return base[:width]

    filler_len = width - base_len
    return base + "─" * filler_len


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

    # Temperature calculations
    temp_celsius = battery.get_float('temperature') / 100.0
    temp_fahrenheit = temp_celsius * 9.0 / 5.0 + 32.0

    # Voltage calculation
    voltage_volts = battery.get_float('voltage') / 1000.0

    # Get colors
    battery_color = get_battery_color(percentage)
    health_color = get_health_color(health_percentage)

    # Layout constants
    inner_width = 44
    blank_inner = " " * inner_width
    solid_line = "-" * inner_width

    # Display header
    print()
    header_title = center_text(f"{Colors.PURPLE}🔋 BATTERY STATUS 🔋{Colors.CYAN}", inner_width)
    print(f"{Colors.CYAN}+{solid_line}+{Colors.RESET}")
    print(f"{Colors.CYAN}|{header_title}|{Colors.RESET}")
    print(f"{Colors.CYAN}+{solid_line}+{Colors.RESET}")
    print()

    # Battery Level Section
    battery_header = create_header_line("Battery Level", inner_width)
    print(f"{Colors.GRAY}+{battery_header}+{Colors.RESET}")

    # Status line
    status_label = " Status:    "
    status_value = f"{status_text:<10} {percentage:>3.0f}% {status_icon:>3s}"
    status_line = f"{status_label}{battery_color}{status_value}{Colors.GRAY}"
    status_line += " " * (inner_width - len(status_label + status_value))
    print(f"{Colors.GRAY}|{status_line}|{Colors.RESET}")

    # Empty line
    print(f"{Colors.GRAY}|{blank_inner}|{Colors.RESET}")

    # Progress bar
    progress_bar = create_progress_bar(percentage, inner_width)
    print(f"{Colors.GRAY}|{battery_color}{progress_bar}{Colors.GRAY}|{Colors.RESET}")
    print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
    print()

    # Battery Health Section
    health_header = create_header_line("Battery Health", inner_width)
    print(f"{Colors.CYAN}+{health_header}+{Colors.RESET}")

    # Health line
    health_label = " Health:    "
    max_cap = battery.get_int('max_capacity')
    design_cap = battery.get_int('design_capacity')
    health_value = f"{health_percentage:>3.0f}% ({max_cap} / {design_cap} mAh)"
    health_line = f"{health_label}{health_color}{health_value}{Colors.GRAY}"
    health_line += " " * (inner_width - len(health_label + health_value))
    print(f"{Colors.GRAY}|{health_line}|{Colors.RESET}")

    # Cycles line
    cycles_label = " Cycles:    "
    cycles = battery.get_int('cycle_count')
    cycles_value = str(cycles)
    cycles_line = f"{cycles_label}{Colors.BLUE}{cycles_value}{Colors.GRAY}"
    cycles_line += " " * (inner_width - len(cycles_label + cycles_value))
    print(f"{Colors.GRAY}|{cycles_line}|{Colors.RESET}")

    print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
    print()

    # Power Details Section
    power_header = create_header_line("Power Details", inner_width)
    print(f"{Colors.PURPLE}+{power_header}+{Colors.RESET}")

    # Voltage line
    voltage_label = " Voltage:   "
    voltage_value = f"{voltage_volts:>6.2f}V"
    voltage_line = f"{voltage_label}{Colors.YELLOW}{voltage_value}{Colors.GRAY}"
    voltage_line += " " * (inner_width - len(voltage_label + voltage_value))
    print(f"{Colors.GRAY}|{voltage_line}|{Colors.RESET}")

    # Current line
    current_label = " Current:   "
    amperage = battery.get_int('amperage')
    current_text, current_color = format_current_draw(amperage)
    current_line = f"{current_label}{current_color}{current_text}{Colors.GRAY}"
    current_line += " " * (inner_width - len(current_label + current_text))
    print(f"{Colors.GRAY}|{current_line}|{Colors.RESET}")

    # Temperature line
    temp_label = " Temp:      "
    temp_value_full = f"{temp_celsius:.1f}°C / {temp_fahrenheit:.1f}°F"
    temp_line = f"{temp_label}{Colors.CYAN}{temp_celsius:.1f}°C{Colors.GRAY} / {temp_fahrenheit:.1f}°F"
    temp_line += " " * (inner_width - len(temp_label + temp_value_full))
    print(f"{Colors.GRAY}|{temp_line}|{Colors.RESET}")

    print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
    print()

    # Time Remaining Section (only if valid time)
    if time_str not in ("Calculating...", "Almost full"):
        time_header = create_header_line("Time Remaining", inner_width)
        print(f"{Colors.GREEN}+{time_header}+{Colors.RESET}")

        time_content = f" {time_str}"
        time_line = f"{time_content}{Colors.GREEN}{time_str}{Colors.GRAY}"
        time_line += " " * (inner_width - len(time_content))
        time_line = time_line.replace(time_str, f"{Colors.GREEN}{time_str}{Colors.GRAY}")
        print(f"{Colors.GRAY}|{' ' + time_str.ljust(inner_width - 1)}|{Colors.RESET}")
        print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
        print()

    # Power Adapter Section (if connected)
    external_connected = battery.get_str('external_connected') == "Yes"

    # Use charger info from system_profiler if available, fallback to ioreg data
    charger_name = charger_info.get('charger_name') or battery.get_str('adapter_name')
    charger_wattage = charger_info.get('charger_wattage')

    if external_connected and charger_name:
        adapter_header = create_header_line("Power Adapter", inner_width)
        print(f"{Colors.BLUE}+{adapter_header}+{Colors.RESET}")

        # Adapter type
        adapter_label = " Type:      "
        adapter_display = truncate_text(charger_name, inner_width - len(adapter_label))
        adapter_line = f"{adapter_label}{Colors.BLUE}{adapter_display}{Colors.GRAY}"
        adapter_line += " " * (inner_width - len(adapter_label + adapter_display))
        print(f"{Colors.GRAY}|{adapter_line}|{Colors.RESET}")

        # Charger wattage from system_profiler (more accurate)
        if charger_wattage:
            watts_label = " Power:     "
            watts_value = f"{charger_wattage}W"
            watts_line = f"{watts_label}{Colors.YELLOW}{watts_value}{Colors.GRAY}"
            watts_line += " " * (inner_width - len(watts_label + watts_value))
            print(f"{Colors.GRAY}|{watts_line}|{Colors.RESET}")
        # Fallback to ioreg adapter watts
        else:
            adapter_watts = battery.get_int('adapter_watts')
            if adapter_watts > 0:
                watts_label = " Power:     "
                watts_value = f"{adapter_watts}W"
                watts_line = f"{watts_label}{Colors.YELLOW}{watts_value}{Colors.GRAY}"
                watts_line += " " * (inner_width - len(watts_label + watts_value))
                print(f"{Colors.GRAY}|{watts_line}|{Colors.RESET}")

        print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
        print()

    # System Info Section
    system_header = create_header_line("System Info", inner_width)
    print(f"{Colors.GRAY}+{system_header}+{Colors.RESET}")

    # Serial number
    serial_label = " Serial:    "
    serial = battery.get_str('serial')
    serial_display = truncate_text(serial, inner_width - len(serial_label))
    serial_line = f"{serial_label}{Colors.GRAY}{serial_display}{Colors.GRAY}"
    serial_line += " " * (inner_width - len(serial_label + serial_display))
    print(f"{Colors.GRAY}|{serial_line}|{Colors.RESET}")

    # Last updated
    updated_label = " Updated:   "
    updated_at = datetime.now().strftime("%H:%M:%S")
    updated_line = f"{updated_label}{Colors.GRAY}{updated_at}{Colors.GRAY}"
    updated_line += " " * (inner_width - len(updated_label + updated_at))
    print(f"{Colors.GRAY}|{updated_line}|{Colors.RESET}")

    print(f"{Colors.GRAY}+{solid_line}+{Colors.RESET}")
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