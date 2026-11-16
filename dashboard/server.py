#!/usr/bin/env python3
"""
Kindle E-Ink Dashboard Server
Hosts HTTP endpoints for touch events, runs periodic data refresh,
and syncs dynamic UI to the Kindle Paperwhite 3.
Directly dispatches hardware commands to Samsung SmartThings.
"""

import os
import sys
import time
import json
import hmac
import logging
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add dashboard to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_service import DataService
from renderer import render_tab, generate_all_screens

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KindleDashboard")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENS_DIR = os.path.join(BASE_DIR, "screens")
os.makedirs(SCREENS_DIR, exist_ok=True)

data_service = DataService()
KINDLE_IP = data_service.config.get("kindle", {}).get("ip", "192.168.1.100")
KINDLE_SSH_KEY = os.path.expanduser(data_service.config.get("kindle", {}).get("ssh_key", "~/.ssh/id_kindle"))
KINDLE_DEST = data_service.config.get("kindle", {}).get("screens_dir", "/mnt/us/dashboard")
current_tab = 0
show_settings = False
last_refresh_time = time.time()
lock = threading.Lock()

def run_ssh_kindle(cmd, timeout=5):
    """Run a shell command on Kindle via SSH."""
    try:
        ssh_cmd = f"ssh -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=3 root@{KINDLE_IP} \"{cmd}\""
        res = subprocess.check_output(ssh_cmd, shell=True, timeout=timeout)
        return res.decode()
    except Exception as e:
        logger.error(f"SSH Kindle error: {e}")
        return None

def push_and_refresh_tab(tab_idx, flash=False):
    """Render a single tab, push to Kindle, and trigger fbink."""
    global current_tab, show_settings
    current_tab = tab_idx
    data = data_service.get_all_data()
    data["show_settings"] = show_settings
    rot = data_service.config.get("kindle", {}).get("rotation", 270)
    data["rotation"] = rot

    # 1. Render & Rotate
    im = render_tab(tab_idx, data)
    rot_file = f"{SCREENS_DIR}/kindle_tab{tab_idx}.png"
    im.rotate(rot, expand=True).save(rot_file)

    # 2. Push via scp
    scp_cmd = f"scp -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no {rot_file} root@{KINDLE_IP}:{KINDLE_DEST}/kindle_tab{tab_idx}.png"
    try:
        subprocess.check_call(scp_cmd, shell=True, timeout=5)
    except Exception as e:
        logger.error(f"SCP error: {e}")
        return

    # 3. Refresh display with fast A2 mode or full flash
    wf_flag = "-f" if flash else "-W A2"
    run_ssh_kindle(f"fbink -g file={KINDLE_DEST}/kindle_tab{tab_idx}.png {wf_flag} >/dev/null 2>&1")
    logger.info(f"Updated and refreshed Tab {tab_idx} on Kindle (settings={show_settings}).")

def do_force_refresh(tab_idx=None):
    """Force re-fetch all data bypassing cache, regenerate all screens, and push to Kindle with full flash."""
    global current_tab, last_refresh_time, show_settings
    if tab_idx is None:
        tab_idx = current_tab
    current_tab = tab_idx
    logger.info(f"Force-refreshing calendar and dashboard data for Tab {tab_idx}...")
    data = data_service.get_all_data(force_refresh=True)
    show_settings = False
    run_ssh_kindle("echo 0 > /mnt/us/dashboard/settings_open")
    data["show_settings"] = False
    rot = data_service.config.get("kindle", {}).get("rotation", 270)
    data["rotation"] = rot
    generate_all_screens(data, SCREENS_DIR, rotation=rot)
    subprocess.call(f"scp -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no {SCREENS_DIR}/kindle_tab*.png root@{KINDLE_IP}:{KINDLE_DEST}/", shell=True)
    push_and_refresh_tab(tab_idx, flash=True)
    last_refresh_time = time.time()
    logger.info("Force refresh complete and pushed to Kindle!")

def handle_tap_action(tab, x, y):
    """Dispatch touch coordinates to real SmartThings hardware, settings drawer, and buttons."""
    global current_tab, show_settings
    smart = data_service.smart_state
    st = data_service.st_client
    logger.info(f"Dispatching tap: Tab {tab} at ({x}, {y}) [settings_open={show_settings}]")

    # 1. GEAR ICON BUTTON TAP IN TOP RIGHT CORNER: [1345..1445, 10..88]
    if 10 <= y <= 88 and x >= 1345:
        show_settings = not show_settings
        logger.info(f"Gear icon tapped! show_settings is now: {show_settings}")
        run_ssh_kindle(f"echo {'1' if show_settings else '0'} > /mnt/us/dashboard/settings_open")
        push_and_refresh_tab(current_tab, flash=False)
        return

    # 2. IF QUICK SETTINGS DRAWER IS OPEN:
    if show_settings:
        # Close Button: [1250, 100, 1425, 160]
        if 1250 <= x <= 1425 and 100 <= y <= 160:
            show_settings = False
            logger.info("Settings Close button tapped.")
            run_ssh_kindle("echo 0 > /mnt/us/dashboard/settings_open")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Brightness [-] Step Down: [790, 210, 875, 280]
        elif 790 <= x <= 875 and 210 <= y <= 280:
            new_val = max(0, data_service.brightness - 3)
            data_service.brightness = new_val
            run_ssh_kindle(f"lipc-set-prop com.lab126.powerd flIntensity {new_val}")
            logger.info(f"Settings Brightness Step Down: {new_val}")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Brightness [+] Step Up: [1275, 210, 1360, 280]
        elif 1275 <= x <= 1360 and 210 <= y <= 280:
            new_val = min(24, data_service.brightness + 3)
            data_service.brightness = new_val
            run_ssh_kindle(f"lipc-set-prop com.lab126.powerd flIntensity {new_val}")
            logger.info(f"Settings Brightness Step Up: {new_val}")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Brightness Slider Track: [880, 215, 1270, 280]
        elif 880 <= x <= 1270 and 215 <= y <= 280:
            frac = (x - 885) / 380.0
            new_val = max(0, min(24, int(round(frac * 24))))
            data_service.brightness = new_val
            run_ssh_kindle(f"lipc-set-prop com.lab126.powerd flIntensity {new_val}")
            logger.info(f"Settings Brightness Slider Tap: {new_val}")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # [ FLIP SCREEN 180° ] Button: [790, 310, 1420, 400]
        elif 790 <= x <= 1420 and 310 <= y <= 400:
            cur_rot = data_service.config.get("kindle", {}).get("rotation", 270)
            new_rot = 90 if cur_rot == 270 else 270
            data_service.config.setdefault("kindle", {})["rotation"] = new_rot
            try:
                with open(data_service.config_path, "w") as f:
                    json.dump(data_service.config, f, indent=2)
            except Exception:
                pass
            run_ssh_kindle(f"echo {new_rot} > /mnt/us/dashboard/rotation")
            logger.info(f"Flipping dashboard orientation to {new_rot} degrees...")
            data = data_service.get_all_data()
            generate_all_screens(data, SCREENS_DIR, rotation=new_rot)
            subprocess.call(f"scp -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no {SCREENS_DIR}/kindle_tab*.png root@{KINDLE_IP}:{KINDLE_DEST}/", shell=True)
            push_and_refresh_tab(current_tab, flash=True)
            return

        # [ FORCE REFRESH ALL DATA ] Button: [790, 420, 1420, 520]
        elif 790 <= x <= 1420 and 420 <= y <= 520:
            logger.info("Settings Force Refresh tapped!")
            do_force_refresh(current_tab)
            return

        # Power Mode: NORMAL [800, 565, 995, 650]
        elif 800 <= x <= 995 and 565 <= y <= 650:
            logger.info("Settings: Power Mode switched to NORMAL")
            data_service.power_mode = "normal"
            data_service.config.setdefault("kindle", {})["power_mode"] = "normal"
            try:
                with open(data_service.config_path, "w") as f:
                    json.dump(data_service.config, f, indent=2)
            except Exception:
                pass
            run_ssh_kindle("echo normal > /mnt/us/dashboard/power_mode")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Power Mode: BATTERY SAVER [1005, 565, 1205, 650]
        elif 1005 <= x <= 1205 and 565 <= y <= 650:
            logger.info("Settings: Power Mode switched to BATTERY SAVER")
            data_service.power_mode = "saver"
            data_service.config.setdefault("kindle", {})["power_mode"] = "saver"
            try:
                with open(data_service.config_path, "w") as f:
                    json.dump(data_service.config, f, indent=2)
            except Exception:
                pass
            run_ssh_kindle("echo saver > /mnt/us/dashboard/power_mode")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Power Mode: ULTRA SAVER [1215, 565, 1410, 650]
        elif 1215 <= x <= 1410 and 565 <= y <= 650:
            logger.info("Settings: Power Mode switched to ULTRA SAVER")
            data_service.power_mode = "ultra"
            data_service.config.setdefault("kindle", {})["power_mode"] = "ultra"
            try:
                with open(data_service.config_path, "w") as f:
                    json.dump(data_service.config, f, indent=2)
            except Exception:
                pass
            run_ssh_kindle("echo ultra > /mnt/us/dashboard/power_mode")
            push_and_refresh_tab(current_tab, flash=False)
            return

        # Tap outside the settings drawer: close it
        elif x < 770 or y > 715:
            show_settings = False
            logger.info("Tap outside settings drawer -> closing.")
            run_ssh_kindle("echo 0 > /mnt/us/dashboard/settings_open")
            push_and_refresh_tab(current_tab, flash=False)
            return

    # 3. IF SETTINGS DRAWER IS CLOSED: NORMAL TAB ACTIONS
    # TAB 0: OVERVIEW REFRESH BUTTON [470, 195, 690, 265]
    if tab == 0:
        if 470 <= x <= 690 and 195 <= y <= 265:
            logger.info("Overview Tab Refresh button tapped! Executing force refresh...")
            do_force_refresh(0)
            return

    # TAB 1: CALENDAR REFRESH BUTTON [460, 195, 690, 260]
    elif tab == 1:
        if 460 <= x <= 690 and 195 <= y <= 260:
            logger.info("Calendar Tab Refresh button tapped! Executing force refresh...")
            do_force_refresh(1)
            return

    # TAB 3: SMART HOME 6-TILE GRID
    elif tab == 3:
        # Col 0: Livingroom TV [45, 220, 465, 580]
        if 45 <= x <= 465 and 220 <= y <= 580:
            cur = smart.get("livingroom_tv", {}).get("switch", "OFF")
            target = "OFF" if cur == "ON" else "ON"
            smart["livingroom_tv"]["switch"] = target
            smart["livingroom_tv"]["active"] = (target == "ON")
            dev_id = st.device_map.get("livingroom_tv", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

        # Col 1: Bedroom TV [510, 220, 930, 580]
        if 510 <= x <= 930 and 220 <= y <= 580:
            cur = smart.get("bedroom_tv", {}).get("switch", "ON")
            target = "OFF" if cur == "ON" else "ON"
            smart["bedroom_tv"]["switch"] = target
            smart["bedroom_tv"]["active"] = (target == "ON")
            dev_id = st.device_map.get("bedroom_tv", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

        # Col 2: Office Monitor [975, 220, 1395, 580]
        if 975 <= x <= 1395 and 220 <= y <= 580:
            cur = smart.get("office_monitor", {}).get("switch", "ON")
            target = "OFF" if cur == "ON" else "ON"
            smart["office_monitor"]["switch"] = target
            smart["office_monitor"]["active"] = (target == "ON")
            dev_id = st.device_map.get("office_monitor", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

        # Row 1 Col 0: Smart Plug [45, 630, 465, 990]
        if 45 <= x <= 465 and 630 <= y <= 990:
            cur = smart.get("smart_plug", {}).get("switch", "ON")
            target = "OFF" if cur == "ON" else "ON"
            smart["smart_plug"]["switch"] = target
            smart["smart_plug"]["active"] = (target == "ON")
            dev_id = st.device_map.get("smart_plug", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

        # Row 1 Col 1: Light 1 [510, 630, 930, 990]
        if 510 <= x <= 930 and 630 <= y <= 990:
            cur = smart.get("light_1", {}).get("switch", "ON")
            target = "OFF" if cur == "ON" else "ON"
            smart["light_1"]["switch"] = target
            smart["light_1"]["active"] = (target == "ON")
            dev_id = st.device_map.get("light_1", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

        # Row 1 Col 2: Lobby [975, 630, 1395, 990]
        if 975 <= x <= 1395 and 630 <= y <= 990:
            cur = smart.get("lobby", {}).get("switch", "ON")
            target = "OFF" if cur == "ON" else "ON"
            smart["lobby"]["switch"] = target
            smart["lobby"]["active"] = (target == "ON")
            dev_id = st.device_map.get("lobby", "") if st else ""
            if dev_id:
                threading.Thread(target=st.toggle_switch, args=(dev_id, cur)).start()
            push_and_refresh_tab(3)
            return

    # TAB 4: TV REMOTE (Livingroom TV via Samsung SmartThings)
    elif tab == 4:
        lr_id = st.device_map.get("livingroom_tv", "") if st else ""

        # 1. TV Power Button: [40, 280, 580, 390]
        if 40 <= x <= 580 and 280 <= y <= 390:
            cur = smart.get("livingroom_tv", {}).get("switch", "OFF")
            target = "OFF" if cur == "ON" else "ON"
            smart["livingroom_tv"]["switch"] = target
            smart["livingroom_tv"]["active"] = (target == "ON")
            if st and lr_id:
                threading.Thread(target=st.tv_power, args=(lr_id, target == "ON")).start()
            logger.info(f"Livingroom TV Power toggled: {target}")
            push_and_refresh_tab(4)
            return

        # 2. HDMI 1: [40, 420, 290, 520]
        elif 40 <= x <= 290 and 420 <= y <= 520:
            smart["livingroom_tv"]["input"] = "HDMI1"
            if st and lr_id:
                threading.Thread(target=st.tv_set_input, args=(lr_id, "HDMI1")).start()
            logger.info("TV Remote: Switched to HDMI 1")
            push_and_refresh_tab(4)
            return

        # 3. HDMI 2: [330, 420, 580, 520]
        elif 330 <= x <= 580 and 420 <= y <= 520:
            smart["livingroom_tv"]["input"] = "HDMI2"
            if st and lr_id:
                threading.Thread(target=st.tv_set_input, args=(lr_id, "HDMI2")).start()
            logger.info("TV Remote: Switched to HDMI 2")
            push_and_refresh_tab(4)
            return

        # 4. VOL +: [40, 650, 290, 770]
        elif 40 <= x <= 290 and 650 <= y <= 770:
            cur_vol = smart.get("livingroom_tv", {}).get("volume", 6)
            smart["livingroom_tv"]["volume"] = min(100, cur_vol + 1)
            smart["livingroom_tv"]["muted"] = False
            if st and lr_id:
                threading.Thread(target=st.tv_volume_up, args=(lr_id,)).start()
            logger.info(f"TV Remote: Volume Up ({smart['livingroom_tv']['volume']})")
            push_and_refresh_tab(4)
            return

        # 5. PLAY / PAUSE: [330, 650, 580, 770]
        elif 330 <= x <= 580 and 650 <= y <= 770:
            if st and lr_id:
                threading.Thread(target=st.tv_play_pause, args=(lr_id,)).start()
            logger.info("TV Remote: Play / Pause toggled")
            return

        # 6. VOL -: [40, 800, 290, 920]
        elif 40 <= x <= 290 and 800 <= y <= 920:
            cur_vol = smart.get("livingroom_tv", {}).get("volume", 6)
            smart["livingroom_tv"]["volume"] = max(0, cur_vol - 1)
            if st and lr_id:
                threading.Thread(target=st.tv_volume_down, args=(lr_id,)).start()
            logger.info(f"TV Remote: Volume Down ({smart['livingroom_tv']['volume']})")
            push_and_refresh_tab(4)
            return

        # 7. MUTE: [330, 800, 580, 920]
        elif 330 <= x <= 580 and 800 <= y <= 920:
            cur_mute = smart.get("livingroom_tv", {}).get("muted", False)
            smart["livingroom_tv"]["muted"] = not cur_mute
            if st and lr_id:
                threading.Thread(target=st.tv_mute, args=(lr_id, not cur_mute)).start()
            logger.info(f"TV Remote: Mute toggled ({not cur_mute})")
            push_and_refresh_tab(4)
            return

        # 8. D-PAD UP: [970, 300, 1130, 430]
        elif 950 <= x <= 1150 and 280 <= y <= 440:
            if st and lr_id:
                threading.Thread(target=st.tv_up, args=(lr_id,)).start()
            logger.info("TV Remote: D-Pad UP")
            return

        # 9. D-PAD LEFT: [840, 445, 970, 575]
        elif 820 <= x <= 975 and 435 <= y <= 585:
            if st and lr_id:
                threading.Thread(target=st.tv_left, args=(lr_id,)).start()
            logger.info("TV Remote: D-Pad LEFT")
            return

        # 10. D-PAD OK: [980, 445, 1120, 575]
        elif 975 <= x <= 1125 and 435 <= y <= 585:
            if st and lr_id:
                threading.Thread(target=st.tv_ok, args=(lr_id,)).start()
            logger.info("TV Remote: D-Pad OK")
            return

        # 11. D-PAD RIGHT: [1130, 445, 1260, 575]
        elif 1125 <= x <= 1280 and 435 <= y <= 585:
            if st and lr_id:
                threading.Thread(target=st.tv_right, args=(lr_id,)).start()
            logger.info("TV Remote: D-Pad RIGHT")
            return

        # 12. D-PAD DOWN: [970, 590, 1130, 720]
        elif 950 <= x <= 1150 and 580 <= y <= 730:
            if st and lr_id:
                threading.Thread(target=st.tv_down, args=(lr_id,)).start()
            logger.info("TV Remote: D-Pad DOWN")
            return

        # 13. BACK: [770, 800, 1020, 920]
        elif 750 <= x <= 1040 and 790 <= y <= 930:
            if st and lr_id:
                threading.Thread(target=st.tv_back, args=(lr_id,)).start()
            logger.info("TV Remote: BACK Pressed")
            return

        # 14. HOME: [1080, 800, 1330, 920]
        elif 1060 <= x <= 1350 and 790 <= y <= 930:
            if st and lr_id:
                threading.Thread(target=st.tv_home, args=(lr_id,)).start()
            logger.info("TV Remote: HOME Pressed")
            return

class DashboardHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global current_tab, show_settings, KINDLE_IP
        client_ip = self.client_address[0]
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # Sanitize query for logging: redact token value
        log_path = parsed.path
        if parsed.query:
            safe_query_parts = []
            for k, v in qs.items():
                if k == "token":
                    safe_query_parts.append(f"{k}=[REDACTED]")
                else:
                    for item in v:
                        safe_query_parts.append(f"{k}={item}")
            if safe_query_parts:
                log_path += "?" + "&".join(safe_query_parts)

        logger.info(f"Incoming HTTP GET from {client_ip}: {log_path}")

        # Shared auth-token check
        auth_token = data_service.config.get("kindle", {}).get("auth_token", "")
        token_valid = False
        if auth_token:
            req_token = qs.get("token", [""])[0] or self.headers.get("X-Auth-Token", "")
            if req_token and hmac.compare_digest(req_token, auth_token):
                token_valid = True

            # Reject requests that are missing the token or have the wrong one,
            # except /health and requests from 127.0.0.1
            if parsed.path != "/health" and client_ip != "127.0.0.1" and not token_valid:
                logger.warning(f"Forbidden 403: unauthorized request from {client_ip} to {parsed.path}")
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Forbidden: Invalid or missing auth token\n")
                return

        # Only update KINDLE_IP from client_address when the request carried a valid token.
        # If no auth_token is configured, do NOT auto-update KINDLE_IP at all. Just use the IP from config.
        if auth_token and token_valid:
            if client_ip != "127.0.0.1" and client_ip != KINDLE_IP:
                logger.info(f"Kindle IP updated from {KINDLE_IP} to {client_ip}")
                KINDLE_IP = client_ip

        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        elif parsed.path == "/set_brightness":
            val = int(qs.get("val", [0])[0])
            val = max(0, min(24, val))
            logger.info(f"Local brightness set from Kindle: {val}")
            with lock:
                data_service.brightness = val
                run_ssh_kindle(f"lipc-set-prop com.lab126.powerd flIntensity {val}")
                push_and_refresh_tab(current_tab)
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path == "/set_rotation":
            rot = int(qs.get("rot", [270])[0])
            with lock:
                data_service.config.setdefault("kindle", {})["rotation"] = rot
                try:
                    with open(data_service.config_path, "w") as f:
                        json.dump(data_service.config, f, indent=2)
                except Exception:
                    pass
                run_ssh_kindle(f"echo {rot} > /mnt/us/dashboard/rotation; echo 0 > /mnt/us/dashboard/settings_open")
                logger.info(f"Rotation set to {rot} degrees...")
                data = data_service.get_all_data()
                generate_all_screens(data, SCREENS_DIR, rotation=rot)
                subprocess.call(f"scp -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no {SCREENS_DIR}/kindle_tab*.png root@{KINDLE_IP}:{KINDLE_DEST}/", shell=True)
                push_and_refresh_tab(current_tab, flash=True)
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path == "/tab_switched":
            tab = int(qs.get("tab", [0])[0])
            logger.info(f"Kindle switched to Tab {tab}")
            with lock:
                current_tab = tab
                if not show_settings:
                    push_and_refresh_tab(tab, flash=False)
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path == "/tick":
            tab = int(qs.get("tab", [current_tab])[0])
            with lock:
                current_tab = tab
                if not show_settings:
                    # Battery-optimized: only push and refresh the single active tab
                    push_and_refresh_tab(tab, flash=False)
                    logger.info(f"Local Kindle RTC tick processed for Tab {tab} (Single screen pushed).")
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path == "/tap":
            tab = int(qs.get("tab", [0])[0])
            x = int(qs.get("x", [0])[0])
            y = int(qs.get("y", [0])[0])
            with lock:
                handle_tap_action(tab, x, y)
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path == "/toggle_settings":
            with lock:
                show_settings = not show_settings
                logger.info(f"Endpoint /toggle_settings called. show_settings={show_settings}")
                run_ssh_kindle(f"echo {'1' if show_settings else '0'} > /mnt/us/dashboard/settings_open")
                push_and_refresh_tab(current_tab, flash=False)
            self.send_response(200)
            self.end_headers()
            return

        elif parsed.path in ["/refresh", "/force_refresh"]:
            tab = int(qs.get("tab", [current_tab])[0])
            with lock:
                do_force_refresh(tab)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Force Refreshed")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def background_sync_worker():
    """Periodic background worker to keep data fresh in memory without waking the Kindle."""
    logger.info("Starting background data refresh loop (15m interval)...")

    while True:
        time.sleep(900)  # Every 15 minutes
        try:
            # Pre-fetch and cache data in memory so Kindle requests are instant
            data_service.get_all_data(force_refresh=False)
        except Exception as e:
            logger.error(f"Periodic background data cache error: {e}")

def main():
    logger.info("==========================================")
    logger.info("Kindle Smart E-Ink Dashboard Server")
    logger.info("==========================================")

    logger.info("Collecting live data & generating screens...")
    bri_out = run_ssh_kindle("lipc-get-prop com.lab126.powerd flIntensity 2>/dev/null")
    if bri_out and bri_out.strip().isdigit():
        data_service.brightness = int(bri_out.strip())
    data = data_service.get_all_data()
    rot = data_service.config.get("kindle", {}).get("rotation", 270)
    run_ssh_kindle(f"echo {rot} > /mnt/us/dashboard/rotation; echo 0 > /mnt/us/dashboard/settings_open")
    generate_all_screens(data, SCREENS_DIR, rotation=rot)

    logger.info(f"Syncing initial screens to Kindle ({KINDLE_IP})...")
    scp_cmd = f"scp -i {KINDLE_SSH_KEY} -o StrictHostKeyChecking=no {SCREENS_DIR}/kindle_tab*.png root@{KINDLE_IP}:{KINDLE_DEST}/"
    subprocess.call(scp_cmd, shell=True, timeout=10)

    logger.info("Displaying Tab 0 on Kindle with full clean flash...")
    run_ssh_kindle(f"fbink -g file={KINDLE_DEST}/kindle_tab0.png -f")

    run_ssh_kindle("killall evtest 2>/dev/null; /mnt/us/dashboard/touch_daemon.sh >/tmp/touch.log 2>&1 &")

    t = threading.Thread(target=background_sync_worker, daemon=True)
    t.start()

    server_address = ("0.0.0.0", 8000)
    httpd = HTTPServer(server_address, DashboardHTTPHandler)
    logger.info("Server listening on http://0.0.0.0:8000")
    logger.info("Ready! Touch any tab or button on your Kindle.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    main()
