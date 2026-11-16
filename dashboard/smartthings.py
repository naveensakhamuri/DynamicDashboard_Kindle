#!/usr/bin/env python3
"""
Samsung SmartThings Integration
Provides real-time state fetching and command execution for Samsung TVs,
TP-Link / Tapo plugs, and smart lights connected to SmartThings.
"""

import json
import time
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("SmartThings")

class SmartThingsClient:
    def __init__(self, token, device_map=None):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.device_map = device_map if device_map is not None else {
            "livingroom_tv": "",
            "bedroom_tv": "",
            "office_monitor": "",
            "smart_plug": "",
            "light_1": "",
            "lobby": ""
        }

    def get_device_status(self, device_id):
        """Fetch current status of a device from SmartThings API."""
        if not device_id:
            return {"switch": "OFF", "active": False, "volume": 10, "muted": False, "input": "HDMI1"}

        url = f"https://api.smartthings.com/v1/devices/{device_id}/status"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                main = data.get("components", {}).get("main", {})
                sw = main.get("switch", {}).get("switch", {}).get("value", "off")
                vol = main.get("audioVolume", {}).get("volume", {}).get("value", None)
                muted = main.get("audioMute", {}).get("mute", {}).get("value", "unmuted") == "muted"
                input_src = main.get("mediaInputSource", {}).get("inputSource", {}).get("value", "HDMI1")
                return {
                    "switch": sw.upper(),
                    "active": (sw.lower() == "on"),
                    "volume": vol,
                    "muted": muted,
                    "input": input_src
                }
        except Exception as e:
            logger.error(f"Error fetching status for {device_id}: {e}")
            return {"switch": "OFF", "active": False, "volume": 10, "muted": False, "input": "HDMI1"}

    def get_all_dashboard_devices(self):
        """Fetch statuses for all 6 dashboard devices."""
        res = {}
        for key, dev_id in self.device_map.items():
            res[key] = self.get_device_status(dev_id)
        return res

    def send_command(self, device_id, capability, command, args=None):
        """Send a command to a SmartThings device with automatic 429 rate-limit backoff."""
        if not device_id:
            logger.warning(f"Cannot send {command}: device_id is not configured")
            return False
        url = f"https://api.smartthings.com/v1/devices/{device_id}/commands"
        cmd_obj = {
            "component": "main",
            "capability": capability,
            "command": command
        }
        if args is not None:
            cmd_obj["arguments"] = args

        body = json.dumps({"commands": [cmd_obj]}).encode("utf-8")

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers=self.headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    logger.info(f"SmartThings command {command} sent to {device_id}: {data}")
                    return True
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:
                    reset_val = e.headers.get("X-RateLimit-Reset", "2000")
                    try:
                        wait_s = max(1.0, min(4.0, float(reset_val) / 1000.0))
                    except Exception:
                        wait_s = 2.0
                    logger.warning(f"SmartThings rate limited (429). Retrying {command} in {wait_s:.1f}s (attempt {attempt+1}/3)...")
                    time.sleep(wait_s)
                    continue
                logger.error(f"SmartThings command error for {device_id} ({command}): {e}")
                return False
            except Exception as e:
                logger.error(f"SmartThings command error for {device_id} ({command}): {e}")
                return False
        return False

    def toggle_switch(self, device_id, current_state="OFF"):
        """Toggle a switch on/off."""
        next_cmd = "off" if current_state.upper() == "ON" else "on"
        return self.send_command(device_id, "switch", next_cmd)

    def tv_power(self, device_id, turn_on=True):
        return self.send_command(device_id, "switch", "on" if turn_on else "off")

    def tv_volume_up(self, device_id):
        return self.send_command(device_id, "audioVolume", "volumeUp")

    def tv_volume_down(self, device_id):
        return self.send_command(device_id, "audioVolume", "volumeDown")

    def tv_mute(self, device_id, mute=True):
        self.send_command(device_id, "samsungvd.remoteControl", "send", ["MUTE"])
        return self.send_command(device_id, "audioMute", "mute" if mute else "unmute")

    def tv_send_key(self, device_id, key):
        """Send a navigation or action key command via samsungvd.remoteControl."""
        return self.send_command(device_id, "samsungvd.remoteControl", "send", [key])

    def tv_play_pause(self, device_id):
        """Send Play/Pause key to TV."""
        return self.tv_send_key(device_id, "PLAY_BACK")

    def tv_up(self, device_id):
        return self.tv_send_key(device_id, "UP")

    def tv_down(self, device_id):
        return self.tv_send_key(device_id, "DOWN")

    def tv_left(self, device_id):
        return self.tv_send_key(device_id, "LEFT")

    def tv_right(self, device_id):
        return self.tv_send_key(device_id, "RIGHT")

    def tv_ok(self, device_id):
        return self.tv_send_key(device_id, "OK")

    def tv_back(self, device_id):
        return self.tv_send_key(device_id, "BACK")

    def tv_home(self, device_id):
        return self.tv_send_key(device_id, "HOME")

    def tv_set_input(self, device_id, input_source):
        """Set input source via mediaInputSource and samsungvd.mediaInputSource."""
        r1 = self.send_command(device_id, "mediaInputSource", "setInputSource", [input_source])
        r2 = self.send_command(device_id, "samsungvd.mediaInputSource", "setInputSource", [input_source])
        return r1 or r2
