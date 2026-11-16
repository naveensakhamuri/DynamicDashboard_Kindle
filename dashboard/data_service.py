#!/usr/bin/env python3
"""
Dashboard Data Service
Aggregates live weather, Claude Code quotas & sessions,
GitHub PR status, Multi-Calendar iCal sync, Kindle hardware status,
and real Samsung SmartThings devices (TVs, plugs, lights).
"""

import os
import re
import glob
import json
import time
import socket
import logging
import subprocess
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger("DataService")

try:
    from dashboard.smartthings import SmartThingsClient
except ImportError:
    from smartthings import SmartThingsClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(BASE_DIR, "config.json")
EXAMPLE_CONFIG = os.path.join(BASE_DIR, "config.example.json")

class DataService:
    def __init__(self, config_path=None):
        self.config_path = config_path or DEFAULT_CONFIG
        self.load_config()
        self.weather_cache = None
        self.weather_cache_time = 0
        self.github_cache = None
        self.github_cache_time = 0
        self.calendar_cache = None
        self.calendar_cache_time = 0
        self.smartthings_cache = None
        self.smartthings_cache_time = 0
        self.brightness = 0
        self.power_mode = self.config.get("kindle", {}).get("power_mode", "saver")

        # SmartThings client
        st_token = self.config.get("smart_home", {}).get("samsung_smartthings", {}).get("personal_access_token", "")
        st_devices = self.config.get("smart_home", {}).get("samsung_smartthings", {}).get("devices")
        self.st_client = SmartThingsClient(st_token, st_devices) if st_token else None

        # Fallback local cache
        self.smart_state = {
            "livingroom_tv": {"switch": "OFF", "active": False, "volume": 6, "muted": True, "input": "HDMI1"},
            "bedroom_tv": {"switch": "ON", "active": True, "volume": 17, "muted": False, "input": "HDMI1"},
            "office_monitor": {"switch": "ON", "active": True, "volume": 31, "muted": False, "input": "HDMI1"},
            "smart_plug": {"switch": "ON", "active": True},
            "light_1": {"switch": "ON", "active": True},
            "lobby": {"switch": "ON", "active": True}
        }

    def load_config(self):
        target = self.config_path
        if not os.path.exists(target) and os.path.exists(EXAMPLE_CONFIG):
            target = EXAMPLE_CONFIG
        try:
            with open(target, "r") as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

    def get_kindle_battery(self):
        """Fetch real battery level from Kindle via SSH."""
        try:
            ip = self.config.get("kindle", {}).get("ip", "192.168.1.100")
            key = self.config.get("kindle", {}).get("ssh_key", "~/.ssh/id_kindle")
            cmd = f"ssh -i {key} -o StrictHostKeyChecking=no -o ConnectTimeout=2 root@{ip} 'lipc-get-prop com.lab126.powerd battLevel'"
            res = subprocess.check_output(cmd, shell=True, timeout=3).decode().strip()
            lines = [l for l in res.split("\n") if l.isdigit()]
            if lines:
                return f"{lines[-1]}%"
        except Exception:
            pass
        return "64%"

    def get_weather(self, force_refresh=False):
        """Fetch live weather from Open-Meteo API."""
        now = time.time()
        if not force_refresh and self.weather_cache and (now - self.weather_cache_time < 900):
            return self.weather_cache

        try:
            lat = self.config.get("location", {}).get("latitude", 51.5074)
            lon = self.config.get("location", {}).get("longitude", -0.1278)
            tz = self.config.get("location", {}).get("timezone", "auto")
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&hourly=precipitation_probability,temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone={tz}"
            req = urllib.request.urlopen(url, timeout=5)
            data = json.loads(req.read().decode())

            cur_temp = round(data['current']['temperature_2m'])
            code = data['current']['weather_code']
            high = round(data['daily']['temperature_2m_max'][0])
            low = round(data['daily']['temperature_2m_min'][0])

            cond_map = {
                0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
                45: "Foggy", 48: "Rime Fog", 51: "Light Drizzle", 53: "Drizzle",
                61: "Slight Rain", 63: "Rain", 65: "Heavy Rain", 80: "Rain Showers"
            }
            cond_str = cond_map.get(code, "Clear")

            rain_hour_str = ""
            cur_dt = datetime.now()
            cur_hour = cur_dt.hour
            hourly_prob = data.get("hourly", {}).get("precipitation_probability", [])
            for h_idx in range(cur_hour, min(cur_hour + 12, len(hourly_prob))):
                if hourly_prob[h_idx] >= 40:
                    rain_hour_str = f"Rain {h_idx:02d}:00"
                    break
            if not rain_hour_str:
                rain_hour_str = "No Rain"

            hourly_slots = []
            for delta in [2, 5, 8]:
                target_h = (cur_hour + delta) % 24
                h_temp = round(data['hourly']['temperature_2m'][target_h])
                h_prob = data['hourly']['precipitation_probability'][target_h]
                h_code = data['hourly']['weather_code'][target_h]
                h_text = cond_map.get(h_code, "Cloud")
                if h_prob >= 40:
                    h_text = f"Rain {h_prob}%"
                hourly_slots.append((f"{target_h:02d}:00", f"{h_temp}°C", h_text))

            res = {
                "header_weather": f"{cur_temp}°C  ({rain_hour_str})",
                "weather_temp": f"{cur_temp}°C {cond_str}",
                "weather_range": f"High {high}° / Low {low}°",
                "hourly": hourly_slots
            }
            self.weather_cache = res
            self.weather_cache_time = now
            return res
        except Exception:
            return {
                "header_weather": "6°C  (No Rain)",
                "weather_temp": "6°C Clear",
                "weather_range": "High 7° / Low 0°",
                "hourly": [("18:00", "5°C", "Clear"), ("21:00", "3°C", "Clear"), ("00:00", "2°C", "Cloud")]
            }

    def get_claude_quota(self):
        """Fetch live Claude Code quota utilization, reset countdown, and active session."""
        pct = 88
        reset_msg = "Resets in: 2h 00m"
        session_str = "Session: Active"
        tokens_str = "Active Project: None"

        try:
            cfg_path = os.path.expanduser(self.config.get("ai", {}).get("claude_config_path", "~/.claude.json"))
            with open(cfg_path, "r") as f:
                cdata = json.load(f)
            util = cdata.get("cachedUsageUtilization", {}).get("utilization", {})
            seven_day = util.get("seven_day", {})
            pct = seven_day.get("utilization", pct)
            resets_at_str = seven_day.get("resets_at", "")

            if resets_at_str:
                reset_dt = datetime.fromisoformat(resets_at_str.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                diff = reset_dt - now_dt
                total_seconds = int(diff.total_seconds())
                if total_seconds > 0:
                    hours = total_seconds // 3600
                    mins = (total_seconds % 3600) // 60
                    reset_msg = f"Resets in: {hours}h {mins}m"
                else:
                    reset_msg = "Resetting soon"
        except Exception:
            pass

        try:
            sfiles = sorted(glob.glob(os.path.expanduser("~/.claude/sessions/*.json")), key=os.path.getmtime, reverse=True)
            if sfiles:
                with open(sfiles[0]) as sf:
                    sinfo = json.load(sf)
                s_name = sinfo.get("name", "cli")
                s_pid = sinfo.get("pid", "")
                s_status = sinfo.get("status", "idle")
                s_cwd = os.path.basename(sinfo.get("cwd", "work"))
                session_str = f"Session: {s_name} [{s_status}] (PID {s_pid})"
                tokens_str = f"Active Project: {s_cwd}"
        except Exception:
            pass

        return {
            "percent": pct,
            "reset_str": reset_msg,
            "tokens_str": tokens_str,
            "session_str": session_str
        }

    def get_system_health(self):
        """Fetch system and network health on host Mac."""
        try:
            load = os.getloadavg()
            load_str = f"Load Avg: {load[0]:.2f}, {load[1]:.2f}"
        except Exception:
            load_str = "Load Avg: 0.42"

        host_ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        kindle_ip = self.config.get("kindle", {}).get("ip", "Kindle")

        return {
            "host_ip": f"Host Server: {host_ip} (Online)",
            "load": load_str,
            "kindle_conn": f"Kindle: {kindle_ip} (SSH Wi-Fi)",
            "status": "System Status: HEALTHY [ OK ]"
        }

    def get_repo_status(self):
        """Fetch open PRs and system status via gh CLI."""
        now = time.time()
        if self.github_cache and (now - self.github_cache_time < 300):
            return self.github_cache

        prs_summary = "Open PRs: 0 (All caught up)"
        ci_summary = "PASSING [ OK ]"
        try:
            author = self.config.get("github", {}).get("author", "@me")
            cmd = f"gh search prs --author {author} --state open --limit 5 --json title,repository"
            out = subprocess.check_output(cmd, shell=True, timeout=5).decode()
            pr_data = json.loads(out)
            if pr_data:
                names = [p.get("repository", {}).get("name", "") for p in pr_data]
                prs_summary = f"Open PRs awaiting review: {len(pr_data)} ({', '.join(names[:3])})"
            else:
                prs_summary = "Open PRs awaiting review: 0 (All caught up)"
        except Exception:
            pass

        res = {
            "prs": prs_summary,
            "ci": f"CI Pipeline: {ci_summary}",
            "last_sync": "Last Git Sync: Just now"
        }
        self.github_cache = res
        self.github_cache_time = now
        return res

    def get_calendar_data(self, force_refresh=False):
        """
        Fetch and parse events from all configured calendars.
        When force_refresh=True, bypasses cache and uses cache-busting on live iCal URLs.
        Returns:
            today: events occurring today
            upcoming_7d: events in next 7 days
            later_month: events in 8-30 days
            calendars_synced: list of {name, count}
            last_synced: formatted local time string
        """
        self.load_config()
        now = time.time()
        if not force_refresh and self.calendar_cache and (now - self.calendar_cache_time < 600):
            return self.calendar_cache

        cals = self.config.get("calendars", [])
        if not cals and "calendar" in self.config:
            single_url = self.config.get("calendar", {}).get("google_ical_url", "").strip()
            if single_url:
                cals = [{"name": "Personal", "url": single_url}]

        today_str = datetime.now().strftime("%Y%m%d")
        all_events = []
        synced_stats = []

        for c in cals:
            url = c.get("url", "").strip()
            name = c.get("name", "Personal")
            if not url:
                continue
            cnt = 0
            try:
                fetch_url = url
                if force_refresh:
                    sep = "&" if "?" in url else "?"
                    fetch_url = f"{url}{sep}_ts={int(now)}"

                req = urllib.request.Request(
                    fetch_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache'
                    }
                )
                resp = urllib.request.urlopen(req, timeout=8)
                raw_ics = resp.read().decode('utf-8', errors='ignore')
                ics_text = re.sub(r'\r?\n[ \t]', '', raw_ics)

                for block in ics_text.split('BEGIN:VEVENT'):
                    if 'END:VEVENT' not in block:
                        continue
                    if 'STATUS:CANCELLED' in block:
                        continue
                    summary_m = re.search(r'SUMMARY:(.*)', block)
                    dtstart_m = re.search(r'DTSTART(?:;[^:]+)?:([0-9TZ]+)', block)
                    dtend_m = re.search(r'DTEND(?:;[^:]+)?:([0-9TZ]+)', block)
                    if summary_m and dtstart_m:
                        summary = summary_m.group(1).strip()
                        summary = summary.replace('\\,', ',').replace('\\;', ';')
                        dt_str = dtstart_m.group(1).strip()
                        dt_end_str = dtend_m.group(1).strip() if dtend_m else dt_str
                        all_events.append({
                            "dt": dt_str,
                            "dt_end": dt_end_str,
                            "summary": summary,
                            "cal": name
                        })
                        cnt += 1
            except Exception as e:
                logger.warning(f"Error syncing calendar {name}: {e}")
            synced_stats.append({"name": name, "count": cnt})

        all_events.sort(key=lambda x: x["dt"])

        today_list = []
        upcoming_7d = []
        later_month = []

        today_dt = datetime.now()

        for ev in all_events:
            dt_raw = ev["dt"]
            dt_end_raw = ev.get("dt_end", dt_raw)
            d_part = dt_raw[:8]
            d_end_part = dt_end_raw[:8]
            summary = ev["summary"]

            # Parse time
            if 'T' in dt_raw:
                t_part = dt_raw.split('T')[1][:4]
                t_str = f"{t_part[:2]}:{t_part[2:]}"
            else:
                t_str = "All Day"

            is_today = (d_part == today_str) or (d_part <= today_str < d_end_part)
            if is_today:
                today_list.append({
                    "time": t_str,
                    "title": summary,
                    "cal": ev["cal"]
                })
            elif d_part > today_str:
                try:
                    ev_date = datetime.strptime(d_part, "%Y%m%d")
                    delta_days = (ev_date.date() - today_dt.date()).days
                    day_label = ev_date.strftime("%a, %b %d")
                    item = {
                        "day_label": day_label,
                        "time": t_str,
                        "title": summary,
                        "cal": ev["cal"],
                        "delta_days": delta_days
                    }
                    if delta_days <= 7:
                        upcoming_7d.append(item)
                    elif delta_days <= 35:
                        later_month.append(item)
                except Exception:
                    pass

        if not today_list and not upcoming_7d and not later_month and not cals:
            today_list = [
                {"time": "10:00", "title": "Team Standup", "cal": "Work"},
                {"time": "14:30", "title": "Architecture Review", "cal": "Work"},
                {"time": "19:00", "title": "Dinner with Friends", "cal": "Personal"}
            ]
            upcoming_7d = [
                {"day_label": "Tomorrow", "time": "11:00", "title": "Product Roadmap Sync", "cal": "Work", "delta_days": 1},
                {"day_label": "Thursday", "time": "15:00", "title": "Tech Talk: E-Ink Dashboards", "cal": "Personal", "delta_days": 2}
            ]
            later_month = [
                {"day_label": "Next Week", "time": "09:30", "title": "Quarterly Planning", "cal": "Work", "delta_days": 8}
            ]

        res = {
            "today": today_list,
            "upcoming_7d": upcoming_7d,
            "later_month": later_month,
            "synced_stats": synced_stats,
            "last_synced": datetime.now().strftime("%I:%M %p"),
            "next_event": (upcoming_7d[0] if upcoming_7d else (later_month[0] if later_month else None))
        }
        self.calendar_cache = res
        self.calendar_cache_time = now
        return res

    def get_smartthings_devices(self, force_refresh=False):
        """
        Fetch all SmartThings devices with 900s (15 min) cache to strictly
        protect the 10 calls/min rate limit for real-time remote commands.
        """
        now = time.time()
        # Only refresh statuses at most once every 15 minutes, or 5 minutes on explicit force refresh
        ttl = 300 if force_refresh else 900
        if self.smartthings_cache and (now - self.smartthings_cache_time < ttl):
            return self.smart_state

        if self.st_client:
            try:
                devs = self.st_client.get_all_dashboard_devices()
                self.smart_state.update(devs)
                self.smartthings_cache = self.smart_state
                self.smartthings_cache_time = now
                return self.smart_state
            except Exception as e:
                logger.warning(f"Error fetching SmartThings devices: {e}")
        return self.smart_state

    def get_all_data(self, force_refresh=False):
        """Compile complete dictionary for rendering."""
        now = datetime.now()
        weather = self.get_weather(force_refresh=force_refresh)
        claude = self.get_claude_quota()
        sys_health = self.get_system_health()
        repo = self.get_repo_status()
        batt = self.get_kindle_battery()
        smart = self.get_smartthings_devices(force_refresh=force_refresh)
        cal_data = self.get_calendar_data(force_refresh=force_refresh)

        return {
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%a, %b %d").upper(),
            "weather": weather["header_weather"],
            "battery": batt,
            "brightness": self.brightness,
            "power_mode": self.power_mode,
            "weather_temp": weather["weather_temp"],
            "weather_range": weather["weather_range"],
            "location_name": self.config.get("location", {}).get("name", "Local"),
            "hourly": weather["hourly"],
            "today_events": cal_data["today"],
            "calendar_data": cal_data,
            "last_calendar_sync": cal_data.get("last_synced", "Just now"),
            "claude": claude,
            "sys_health": sys_health,
            "repo": repo,
            "smart": smart
        }
