#!/bin/sh
# Kindle E-Ink Dashboard Touch Daemon
# Runs evtest inside a PTY via /usr/bin/script to eliminate stdout buffering.
# Supports 5 Tabs: OVERVIEW, CALENDAR, AI & DEV, SMART HOME, TV REMOTE.
# Supports dynamic orientation: 90 (standard) and 270 (upside down).
# Battery-Optimized: Wi-Fi power saving, CPU scaling, smart interval, zero-idle frontlight.

# Prevent Kindle from ever sleeping or activating screensaver
lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null || true

# Stop native Amazon GUI so it never overwrites the framebuffer
stop lab126_gui 2>/dev/null || true
stop framework 2>/dev/null || true
killall -9 awesome cvm 2>/dev/null || true

# Ensure Dropbear SSH daemon is always running on Wi-Fi
if ! pidof dropbear >/dev/null 2>&1; then
    [ -x /mnt/us/usbnet/bin/dropbear ] && /mnt/us/usbnet/bin/dropbear -p 22 2>/dev/null || true
fi

# Power optimizations: enable Wi-Fi power management & on-demand CPU scaling
iwconfig wlan0 power on 2>/dev/null || true
echo ondemand > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true

echo 0 > /mnt/us/dashboard/current_tab
echo 0 > /mnt/us/dashboard/settings_open
[ -f /mnt/us/dashboard/rotation ] || echo 270 > /mnt/us/dashboard/rotation
[ -f /mnt/us/dashboard/power_mode ] || echo saver > /mnt/us/dashboard/power_mode
lipc-get-prop com.lab126.powerd flIntensity > /mnt/us/dashboard/brightness 2>/dev/null || echo 0 > /mnt/us/dashboard/brightness

# Host server IP (pass as first argument or via KINDLE_HOST_IP env var, default 192.168.1.100)
HOST_IP="${1:-${KINDLE_HOST_IP:-192.168.1.100}}"

# Kill any previous ticker instances
killall -9 sleep 2>/dev/null || true

# Draw current dashboard immediately on startup
fbink -g file=/mnt/us/dashboard/kindle_tab0.png -f >/dev/null 2>&1

# Hardware Clock Ticker (Supports 3 Modes: normal, saver, ultra)
(
    while true; do
        lipc-set-prop com.lab126.powerd preventScreenSaver 1 2>/dev/null || true
        
        # Read active power mode (normal, saver, ultra)
        MODE="saver"
        [ -f /mnt/us/dashboard/power_mode ] && MODE=$(cat /mnt/us/dashboard/power_mode 2>/dev/null)
        [ -z "$MODE" ] && MODE="saver"

        HOUR=$(date +%H | sed 's/^0*//')
        [ -z "$HOUR" ] && HOUR=0

        # --- MODE 1: NORMAL (Original 1-minute live ticker, no battery throttling) ---
        if [ "$MODE" = "normal" ]; then
            SEC=$(date +%S | sed 's/^0*//')
            [ -z "$SEC" ] && SEC=0
            SLEEP_TIME=$((60 - SEC))
            [ "$SLEEP_TIME" -le 0 ] && SLEEP_TIME=60

        # --- MODE 2: BATTERY SAVER (5-minute sync, Wi-Fi sleep, Night mode, NO plug-detect) ---
        elif [ "$MODE" = "saver" ]; then
            # Night Mode (11 PM - 7 AM): Frontlight 0, sleep 30 mins
            if [ "$HOUR" -ge 23 ] || [ "$HOUR" -lt 7 ]; then
                lipc-set-prop com.lab126.powerd flIntensity 0 2>/dev/null || true
                sleep 1800
                CUR_TAB=$(cat /mnt/us/dashboard/current_tab 2>/dev/null || echo 0)
                curl -s --connect-timeout 4 "http://$HOST_IP:8000/tick?tab=$CUR_TAB&ts=$(date +%s)" >/dev/null 2>&1
                continue
            fi

            # Daytime: 5-minute sync aligned to clock
            MIN=$(date +%M | sed 's/^0*//')
            [ -z "$MIN" ] && MIN=0
            SEC=$(date +%S | sed 's/^0*//')
            [ -z "$SEC" ] && SEC=0
            REM=$((5 - (MIN % 5)))
            SLEEP_TIME=$(((REM * 60) - SEC))
            [ "$SLEEP_TIME" -le 0 ] && SLEEP_TIME=300

        # --- MODE 3: ULTRA BATTERY SAVER (All optimizations + Smart plug detection) ---
        else
            CHARGING=$(lipc-get-prop com.lab126.powerd isCharging 2>/dev/null || echo 0)
            if [ "$CHARGING" = "1" ]; then
                # Plugged into USB power: full 1-minute ticker
                SEC=$(date +%S | sed 's/^0*//')
                [ -z "$SEC" ] && SEC=0
                SLEEP_TIME=$((60 - SEC))
                [ "$SLEEP_TIME" -le 0 ] && SLEEP_TIME=60
            else
                # On battery:
                # Night Mode (11 PM - 7 AM): Frontlight 0, sleep 60 mins
                if [ "$HOUR" -ge 23 ] || [ "$HOUR" -lt 7 ]; then
                    lipc-set-prop com.lab126.powerd flIntensity 0 2>/dev/null || true
                    sleep 3600
                    CUR_TAB=$(cat /mnt/us/dashboard/current_tab 2>/dev/null || echo 0)
                    curl -s --connect-timeout 4 "http://$HOST_IP:8000/tick?tab=$CUR_TAB&ts=$(date +%s)" >/dev/null 2>&1
                    continue
                fi

                # Daytime: 15-minute sync aligned to clock
                MIN=$(date +%M | sed 's/^0*//')
                [ -z "$MIN" ] && MIN=0
                SEC=$(date +%S | sed 's/^0*//')
                [ -z "$SEC" ] && SEC=0
                REM=$((15 - (MIN % 15)))
                SLEEP_TIME=$(((REM * 60) - SEC))
                [ "$SLEEP_TIME" -le 0 ] && SLEEP_TIME=900
            fi
        fi

        sleep "$SLEEP_TIME"
        CUR_TAB=$(cat /mnt/us/dashboard/current_tab 2>/dev/null || echo 0)
        curl -s --connect-timeout 4 "http://$HOST_IP:8000/tick?tab=$CUR_TAB&ts=$(date +%s)" >/dev/null 2>&1
    done
) &

echo "[Touch Daemon] Starting touch listener on /dev/input/event1 with smart battery ticker..."

/usr/bin/script -q -c "/mnt/us/usbnet/bin/evtest /dev/input/event1" /dev/null | awk -v host="$HOST_IP" '
BEGIN {
    cur_tab = 0;
    raw_x = 0;
    raw_y = 0;
    cur_bri = 0;
    cur_rot = 270;
}
/code 53 \(ABS_MT_POSITION_X\)/ { raw_x = $NF }
/code 54 \(ABS_MT_POSITION_Y\)/ { raw_y = $NF }
/code 330 \(BTN_TOUCH\), value 0/ {
    # Read current screen rotation (90 or 270)
    getline cur_rot < "/mnt/us/dashboard/rotation";
    close("/mnt/us/dashboard/rotation");
    if (cur_rot != 90 && cur_rot != 270) cur_rot = 270;

    # Read settings drawer state (0 = closed, 1 = open)
    settings_open = 0;
    if ((getline s_open < "/mnt/us/dashboard/settings_open") > 0) {
        settings_open = s_open;
    }
    close("/mnt/us/dashboard/settings_open");

    # Dynamic Coordinate Transformation:
    # When rot == 270 (upside down landscape): X = raw_y, Y = 1071 - raw_x
    # When rot == 90 (standard landscape):    X = 1447 - raw_y, Y = raw_x
    if (cur_rot == 270) {
        x_l = raw_y;
        y_l = 1071 - raw_x;
    } else {
        x_l = 1447 - raw_y;
        y_l = raw_x;
    }

    print "[TOUCH rot=" cur_rot " settings=" settings_open "] Raw:(" raw_x "," raw_y ") -> Landscape:(" x_l "," y_l ")";
    fflush();

    # 1. GEAR ICON TAP IN TOP RIGHT CORNER: [1345..1447, 10..88]
    if (y_l >= 10 && y_l <= 88 && x_l >= 1345) {
        print "[GEAR] Gear icon tapped! Toggling settings...";
        fflush();
        system("curl -s --connect-timeout 3 \"http://" host ":8000/toggle_settings\" >/dev/null 2>&1 &");
    }
    # 1b. CLOCK / HEADER TAP: Instant force refresh
    else if (y_l >= 10 && y_l <= 88 && x_l < 1345) {
        print "[HEADER] Clock/Header tapped! Instant refresh...";
        fflush();
        system("curl -s --connect-timeout 3 \"http://" host ":8000/force_refresh?tab=" cur_tab "\" >/dev/null 2>&1 &");
    }
    # 2. IF SETTINGS DRAWER IS OPEN: All taps go directly to /tap
    else if (settings_open == 1) {
        print "[SETTINGS TAP] Tab " cur_tab " @ (" x_l "," y_l ")";
        fflush();
        system("curl -s --connect-timeout 3 \"http://" host ":8000/tap?tab=" cur_tab "&x=" x_l "&y=" y_l "\" >/dev/null 2>&1 &");
    }
    # 3. IF SETTINGS DRAWER IS CLOSED:
    # A) HEADER TABS AREA: Y_L between 88 and 180 (5 equal tabs: 285px each)
    else if (y_l > 88 && y_l <= 180) {
        new_tab = cur_tab;
        if (x_l < 295) {
            new_tab = 0;
        } else if (x_l < 580) {
            new_tab = 1;
        } else if (x_l < 865) {
            new_tab = 2;
        } else if (x_l < 1150) {
            new_tab = 3;
        } else {
            new_tab = 4;
        }

        if (new_tab != cur_tab) {
            cur_tab = new_tab;
            print "[TAB SWITCH] Switching to Tab " cur_tab;
            fflush();
            system("echo " cur_tab " > /mnt/us/dashboard/current_tab");
            system("fbink -g file=/mnt/us/dashboard/kindle_tab" cur_tab ".png -W A2 >/dev/null 2>&1");
            system("curl -s --connect-timeout 2 \"http://" host ":8000/tab_switched?tab=" cur_tab "\" >/dev/null 2>&1 &");
        }
    }
    # B) CONTENT AREA: Y_L > 180
    else if (y_l > 180) {
        print "[ACTION TAP] Tab " cur_tab " @ (" x_l "," y_l ")";
        fflush();
        system("curl -s --connect-timeout 2 \"http://" host ":8000/tap?tab=" cur_tab "&x=" x_l "&y=" y_l "\" >/dev/null 2>&1 &");
    }
}
'
