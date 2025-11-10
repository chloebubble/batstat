#!/usr/bin/env fish

# Battery Status Script - batstat
# A beautiful battery status display for macOS using ioreg

function batstat
    # Get battery data from ioreg
    set battery_data (ioreg -lrn AppleSmartBattery 2>/dev/null)

    if test -z "$battery_data"
        echo "❌ Unable to read battery information"
        return 1
    end

    # Extract key battery metrics
    set current_capacity (echo "$battery_data" | grep '"CurrentCapacity" = ' | sed 's/.*= //')
    set max_capacity (echo "$battery_data" | grep '"MaxCapacity" = ' | sed 's/.*= //')
    set design_capacity (echo "$battery_data" | grep '"DesignCapacity" = ' | sed 's/.*= //')
    set cycle_count (echo "$battery_data" | grep '"CycleCount" = ' | sed 's/.*= //')
    set temperature (echo "$battery_data" | grep '"Temperature" = ' | sed 's/.*= //')
    set voltage (echo "$battery_data" | grep '"Voltage" = ' | sed 's/.*= //')
    set amperage (echo "$battery_data" | grep '"Amperage" = ' | sed 's/.*= //')
    set is_charging (echo "$battery_data" | grep '"IsCharging" = ' | sed 's/.*= //')
    set external_connected (echo "$battery_data" | grep '"ExternalConnected" = ' | sed 's/.*= //')
    set fully_charged (echo "$battery_data" | grep '"FullyCharged" = ' | sed 's/.*= //')
    set time_remaining (echo "$battery_data" | grep '"TimeRemaining" = ' | sed 's/.*= //')
    set serial (echo "$battery_data" | grep '"Serial" = ' | sed 's/.*= \"\([^\"]*\)\".*/\1/')
    set adapter_name (echo "$battery_data" | grep '"Name" = ' | sed 's/.*= \"\([^\"]*\)\".*/\1/' | head -1)
    set adapter_watts (echo "$battery_data" | grep '"Watts" = ' | sed 's/.*= //' | head -1)

    # Convert values to more readable formats
    set percentage (math "scale=1; $current_capacity * 100 / $max_capacity")
    set temp_celsius (math "scale=1; $temperature / 100")
    set temp_fahrenheit (math "scale=1; $temp_celsius * 9 / 5 + 32")
    set voltage_volts (math "scale=2; $voltage / 1000")

    # Calculate health percentage
    set health_percent (math "scale=1; $max_capacity * 100 / $design_capacity")

    # Determine charging status
    set status_icon "🔋"
    set status_text "Discharging"

    if test "$is_charging" = "Yes"
        set status_icon "⚡"
        set status_text "Charging"
    else if test "$external_connected" = "Yes" -a "$fully_charged" = "Yes"
        set status_icon "🔌"
        set status_text "Fully Charged"
    else if test "$external_connected" = "Yes"
        set status_icon "🔌"
        set status_text "Not Charging"
    end

    # Format time remaining
    set time_str "Calculating..."
    if test "$time_remaining" != "65535" -a "$time_remaining" != "-1"
        if test "$time_remaining" -gt 0
            set hours (math "$time_remaining / 60")
            set minutes (math "$time_remaining % 60")
            set time_str (printf "%dh %dm" $hours $minutes)
        else
            set time_str "Almost full"
        end
    else if test "$is_charging" != "Yes"
        set time_str "Calculating..."
    end

    # Color codes for terminal output
    set color_reset (set_color normal)
    set color_green (set_color green)
    set color_yellow (set_color yellow)
    set color_orange (set_color brorange)
    set color_red (set_color red)
    set color_blue (set_color blue)
    set color_purple (set_color purple)
    set color_cyan (set_color cyan)
    set color_gray (set_color 666)

    # Choose color based on battery level
    set battery_color $color_green
    if test $percentage -le 20
        set battery_color $color_red
    else if test $percentage -le 40
        set battery_color $color_orange
    else if test $percentage -le 60
        set battery_color $color_yellow
    end

    # Choose health color
    set health_color $color_green
    if test $health_percent -le 60
        set health_color $color_red
    else if test $health_percent -le 80
        set health_color $color_yellow
    end

    # Display header
    echo
    echo "$color_cyan"╭─────────────────────────────────────────╮"$color_reset"
    echo "$color_cyan"│"$color_purple"          🔋 BATTERY STATUS 🔋          "$color_cyan"│"$color_reset"
    echo "$color_cyan"╰─────────────────────────────────────────╯"$color_reset"
    echo

    # Battery Level Section
    echo "$color_gray┌─ Battery Level ─────────────────────────┐"$color_reset"
    printf "$color_gray│ Status:    %s%-10s%s %s%3d%%%s %s%3s%s │\n" \
        "$battery_color" "$status_text" "$color_reset" \
        "$battery_color" "$percentage" "$color_reset" \
        "$color_gray" "$status_icon" "$color_reset"
    echo "$color_gray│                                            │"$color_reset"

    # Progress bar
    set bar_length 40
    set filled_length (math "scale=0; $percentage * $bar_length / 100")
    set empty_length (math "$bar_length - $filled_length")

    set progress_bar ""
    for i in (seq 1 $filled_length)
        set progress_bar $progress_bar"█"
    end
    for i in (seq 1 $empty_length)
        set progress_bar $progress_bar"░"
    end

    printf "$color_gray│ %s%s%s%s │\n" \
        "$battery_color" "$progress_bar" "$color_reset" "$color_gray"
    echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
    echo

    # Health Section
    echo "$color_cyan┌─ Battery Health ─────────────────────────┐"$color_reset"
    printf "$color_gray│ Health:    %s%-3d%%%s (%d / %d mAh)      │\n" \
        "$health_color" "$health_percent" "$color_reset" \
        "$max_capacity" "$design_capacity"
    printf "$color_gray│ Cycles:    %s%d%s                        │\n" \
        "$color_blue" "$cycle_count" "$color_reset"
    echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
    echo

    # Power Section
    echo "$color_purple┌─ Power Details ─────────────────────────┐"$color_reset"
    printf "$color_gray│ Voltage:   %s%.2fV%s                     │\n" \
        "$color_yellow" "$voltage_volts" "$color_reset"

    if test "$amperage" != "0"
        set current_ma (math "scale=0; $amperage")
        if test $current_ma -gt 0
            printf "$color_gray│ Current:   %s+%dmA%s (charging)         │\n" \
                "$color_green" "$current_ma" "$color_reset"
        else
            printf "$color_gray│ Current:   %s%dmA%s (drawing)           │\n" \
                "$color_orange" (math "$current_ma * -1") "$color_reset"
        end
    else
        printf "$color_gray│ Current:   %s0mA%s (idle)                 │\n" \
            "$color_gray" "$color_reset"
    end

    printf "$color_gray│ Temp:      %s%.1f°C%s / %.1f°F            │\n" \
        "$color_cyan" "$temp_celsius" "$color_reset" "$temp_fahrenheit"
    echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
    echo

    # Time Section
    if test "$time_str" != "Calculating..." -a "$time_str" != "Almost full"
        echo "$color_green┌─ Time Remaining ────────────────────────┐"$color_reset"
        printf "$color_gray│ %s%-40s%s │\n" \
            "$color_green" "$time_str" "$color_reset"
        echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
        echo
    end

    # Adapter Info Section
    if test "$external_connected" = "Yes" -a -n "$adapter_name"
        echo "$color_blue┌─ Power Adapter ──────────────────────────┐"$color_reset"
        printf "$color_gray│ Type:      %s%s%s                    │\n" \
            "$color_blue" "$adapter_name" "$color_reset"
        if test -n "$adapter_watts"
            printf "$color_gray│ Power:     %s%dW%s                       │\n" \
                "$color_yellow" "$adapter_watts" "$color_reset"
        end
        echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
        echo
    end

    # System Info Section
    echo "$color_gray┌─ System Info ────────────────────────────┐"$color_reset"
    printf "$color_gray│ Serial:    %s%s%s                      │\n" \
        "$color_gray" "$serial" "$color_reset"
    printf "$color_gray│ Updated:   %s%s%s        │\n" \
        "$color_gray" (date '+%H:%M:%S') "$color_reset"
    echo "$color_gray└────────────────────────────────────────────┘"$color_reset"
    echo
end

# Run the function if script is executed directly
if test (basename (status -f)) = "batstat.fish"
    batstat $argv
end