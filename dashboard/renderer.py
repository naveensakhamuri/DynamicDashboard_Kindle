#!/usr/bin/env python3
"""
Kindle E-Ink Dashboard Renderer
Resolution: 1448 x 1072 (Paperwhite 3 Landscape)
5 Tabs: OVERVIEW, CALENDAR, AI & DEV, SMART HOME, TV REMOTE.
- Overview has dedicated large-font Today's Schedule (quick actions removed).
- Calendar tab displays multi-day detailed events from all synced calendars.
- Smart Home toggles: BLACK background = OFF, WHITE background = ON.
- Persistent top header with hardware brightness slider and rotate button.
"""

import os
import sys
import math
import json
from collections import OrderedDict
from PIL import Image, ImageDraw, ImageFont

def get_font(font_name, size, is_mono=False):
    """Load font with platform-independent fallbacks."""
    candidates = []
    if sys.platform == "darwin":
        if is_mono:
            candidates = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Monaco.dfont"]
        else:
            candidates = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNSText.ttf", "/System/Library/Fonts/Arial.ttf"]
    elif sys.platform.startswith("linux"):
        if is_mono:
            candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/TTF/DejaVuSansMono.ttf"]
        else:
            candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSans.ttf"]
    else:
        if is_mono:
            candidates = ["consola.ttf", "cour.ttf"]
        else:
            candidates = ["arial.ttf", "calibri.ttf"]

    for path in candidates:
        if os.path.exists(path) or not os.path.isabs(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()

FONT_HERO = get_font("Helvetica", 40)
FONT_TITLE = get_font("Helvetica", 34)
FONT_BOLD = get_font("Helvetica", 28)
FONT_MED = get_font("Helvetica", 24)
FONT_SMALL = get_font("Helvetica", 20)
FONT_MODE_TITLE = get_font("Helvetica", 18)
FONT_MODE_SUB = get_font("Helvetica", 15)
FONT_MONO = get_font("Menlo", 24, is_mono=True)
FONT_MONO_BOLD = get_font("Menlo", 30, is_mono=True)

def draw_hatch(draw, bbox, step=10, width=2):
    """Draw faux 1-bit hatching pattern inside bbox (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = bbox
    for d in range(- (y2 - y1), (x2 - x1) + (y2 - y1), step):
        sx = x1 + d
        sy = y1
        ex = sx + (y2 - y1)
        ey = y2
        draw.line([sx, sy, ex, ey], fill=0, width=width)

def draw_progress_bar(draw, x, y, w, h, percent, label=""):
    """Draw a progress bar with faux hatching fill."""
    draw.rectangle([x, y, x + w, y + h], outline=0, width=3)
    fill_w = int((w - 6) * (percent / 100.0))
    if fill_w > 0:
        hatch_box = (x + 3, y + 3, x + 3 + fill_w, y + h - 3)
        draw_hatch(draw, hatch_box, step=8, width=2)
    if label:
        draw.text((x + w + 15, y + 2), f"{percent}% {label}", font=FONT_BOLD, fill=0)

def draw_gear_icon(draw, cx, cy, radius=18, fill=0, bg_color=255):
    """Draw crisp 8-tooth mechanical gear icon without Unicode font dependencies."""
    teeth = 8
    tooth_w = max(4, int(radius * 0.35))
    for i in range(teeth):
        angle = i * (2 * math.pi / teeth)
        tx = cx + radius * math.cos(angle)
        ty = cy + radius * math.sin(angle)
        draw.line([cx, cy, tx, ty], fill=fill, width=tooth_w)
    draw.ellipse([cx - radius * 0.72, cy - radius * 0.72, cx + radius * 0.72, cy + radius * 0.72], fill=fill)
    draw.ellipse([cx - radius * 0.32, cy - radius * 0.32, cx + radius * 0.32, cy + radius * 0.32], fill=bg_color)

def draw_refresh_icon(draw, cx, cy, radius=14, width=3, fill=0):
    """Draw circular refresh arrow icon without Unicode font dependencies."""
    draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=45, end=330, fill=fill, width=width)
    rad = math.radians(45)
    ax = cx + radius * math.cos(rad)
    ay = cy + radius * math.sin(rad)
    draw.polygon([(ax - 2, ay - 6), (ax + 7, ay - 1), (ax - 1, ay + 6)], fill=fill)

def draw_rotate_icon(draw, cx, cy, radius=14, width=3, fill=0):
    """Draw dual curved 180-degree flip arrow icon without Unicode font dependencies."""
    draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=30, end=150, fill=fill, width=width)
    draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=210, end=330, fill=fill, width=width)
    draw.polygon([(cx - radius - 4, cy - 2), (cx - radius + 4, cy - 2), (cx - radius, cy + 6)], fill=fill)
    draw.polygon([(cx + radius - 4, cy + 2), (cx + radius + 4, cy + 2), (cx + radius, cy - 6)], fill=fill)

def draw_close_icon(draw, cx, cy, size=10, width=3, fill=0):
    """Draw diagonal cross (X) close icon."""
    draw.line([cx - size, cy - size, cx + size, cy + size], fill=fill, width=width)
    draw.line([cx - size, cy + size, cx + size, cy - size], fill=fill, width=width)

def draw_check_icon(draw, cx, cy, size=14, width=3, fill=0):
    """Draw crisp checkmark icon."""
    s = size
    draw.line([cx - s * 0.5, cy, cx - s * 0.15, cy + s * 0.45], fill=fill, width=width)
    draw.line([cx - s * 0.15, cy + s * 0.45, cx + s * 0.55, cy - s * 0.45], fill=fill, width=width)

def draw_triangle(draw, cx, cy, size=14, direction='up', fill=0):
    """Draw crisp solid directional arrow triangle."""
    s = size
    if direction == 'up':
        pts = [(cx, cy - s), (cx - s * 0.85, cy + s * 0.6), (cx + s * 0.85, cy + s * 0.6)]
    elif direction == 'down':
        pts = [(cx, cy + s), (cx - s * 0.85, cy - s * 0.6), (cx + s * 0.85, cy - s * 0.6)]
    elif direction == 'left':
        pts = [(cx - s, cy), (cx + s * 0.6, cy - s * 0.85), (cx + s * 0.6, cy + s * 0.85)]
    elif direction == 'right':
        pts = [(cx + s, cy), (cx - s * 0.6, cy - s * 0.85), (cx - s * 0.6, cy + s * 0.85)]
    draw.polygon(pts, fill=fill)

def draw_toggle_tile(draw, bbox, title, lines, is_on=False):
    """
    Draw a smart home device toggle tile.
    USER RULE: Black is used as OFF, White is used as ON.
    """
    x1, y1, x2, y2 = bbox
    if is_on:
        # ON: White background, black text
        draw.rectangle([x1, y1, x2, y2], fill=255, outline=0, width=4)
        draw.rectangle([x1 + 4, y1 + 4, x2 - 4, y2 - 4], outline=0, width=1)
        text_color = 0
    else:
        # OFF: Solid black background, white text
        draw.rectangle([x1, y1, x2, y2], fill=0, outline=0, width=4)
        draw.rectangle([x1 + 4, y1 + 4, x2 - 4, y2 - 4], outline=255, width=1)
        text_color = 255

    cy = (y1 + y2) // 2
    if len(lines) == 1:
        draw.text((x1 + 24, cy - 24), title, font=FONT_BOLD, fill=text_color)
        draw.text((x1 + 24, cy + 10), lines[0], font=FONT_MED, fill=text_color)
    elif len(lines) >= 2:
        draw.text((x1 + 24, cy - 36), title, font=FONT_BOLD, fill=text_color)
        draw.text((x1 + 24, cy - 2), lines[0], font=FONT_MED, fill=text_color)
        draw.text((x1 + 24, cy + 30), lines[1], font=FONT_SMALL, fill=text_color)

def draw_header_and_tabs(draw, active_tab=0, header_data=None):
    """Draw persistent top header (85px) and 5 centered navigation tabs (76px)."""
    w, h = 1448, 1072

    time_str = header_data.get("time", "04:45 PM") if header_data else "04:45 PM"
    date_str = header_data.get("date", "FRI, NOV 13") if header_data else "FRI, NOV 13"
    weather_str = header_data.get("weather", "6°C Clear") if header_data else "6°C Clear"
    weather_range = header_data.get("weather_range", "") if header_data else ""
    batt_str = header_data.get("battery", "64%") if header_data else "64%"
    show_settings = header_data.get("show_settings", False) if header_data else False

    # 1. Top Header Bar: [10, 10, w - 10, 85]
    draw.rectangle([10, 10, w - 10, 85], outline=0, width=4)

    # Left: Clock & Date
    draw.text((25, 23), time_str, font=FONT_TITLE, fill=0)
    draw.text((215, 28), f"•  {date_str}", font=FONT_BOLD, fill=0)

    # Center: Weather + High/Low Range
    weather_display = f"{weather_str}   ({weather_range})" if weather_range else weather_str
    draw.text((510, 27), weather_display, font=FONT_BOLD, fill=0)

    # Right: Battery & Gear Icon Button
    draw.text((1205, 28), f"BAT {batt_str}", font=FONT_BOLD, fill=0)

    # [ Gear ] Button in Top Right Corner: [1360, 15, 1435, 80]
    gear_cx = 1360 + 75 // 2
    gear_cy = 15 + 65 // 2
    if show_settings:
        draw.rectangle([1360, 15, 1435, 80], fill=0, outline=0, width=3)
        draw_gear_icon(draw, gear_cx, gear_cy, radius=20, fill=255, bg_color=0)
    else:
        draw.rectangle([1360, 15, 1435, 80], fill=255, outline=0, width=3)
        draw.rectangle([1364, 19, 1431, 76], outline=0, width=1)
        draw_gear_icon(draw, gear_cx, gear_cy, radius=20, fill=0, bg_color=255)

    # 2. Tabs Bar (5 equal tabs)
    tabs = ["OVERVIEW", "CALENDAR", "AI & DEV", "SMART HOME", "TV REMOTE"]
    tab_w = (w - 20) // 5
    tab_y1 = 92
    tab_y2 = 168

    for i, tab in enumerate(tabs):
        tx1 = 10 + i * tab_w
        tx2 = tx1 + tab_w
        is_active = (i == active_tab)
        tab_text = f"[ {tab} ]" if is_active else tab
        fill_color = 255 if is_active else 0
        bg_color = 0 if is_active else 255

        draw.rectangle([tx1, tab_y1, tx2, tab_y2], fill=bg_color, outline=0, width=3)

        # Precise text centering calculation
        bbox = draw.textbbox((0, 0), tab_text, font=FONT_BOLD)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = tx1 + (tab_w - tw) // 2 - bbox[0]
        ty = tab_y1 + ((tab_y2 - tab_y1) - th) // 2 - bbox[1]
        draw.text((tx, ty), tab_text, font=FONT_BOLD, fill=fill_color)

    # Main Canvas Border
    draw.rectangle([10, 175, w - 10, h - 10], outline=0, width=4)

def draw_settings_dropdown(draw, data=None):
    """
    Draw a clean, high-contrast Settings & Controls drawer directly under the Gear icon.
    Contains:
      - Brightness slider bar (interactive [-], track, [+])
      - Orientation flip button [ FLIP SCREEN 180° ]
      - Force refresh button [ FORCE REFRESH ALL DATA ]
      - [ CLOSE ] button
    """
    w, h = 1448, 1072
    bri_val = data.get("brightness", 18) if data else 18
    bri_val = max(0, min(24, int(bri_val)))
    cur_rot = data.get("rotation", 270) if data else 270
    last_sync = data.get("last_calendar_sync", "Just now") if data else "Just now"

    # Box coordinates: [770, 88, 1435, 715]
    bx1, by1, bx2, by2 = 770, 88, 1435, 715

    # Solid white background with drop-shadow border
    draw.rectangle([bx1 + 6, by1 + 6, bx2 + 6, by2 + 6], fill=0)
    draw.rectangle([bx1, by1, bx2, by2], fill=255, outline=0, width=5)
    draw.rectangle([bx1 + 4, by1 + 4, bx2 - 4, by2 - 4], outline=0, width=1)

    # Header Row: Title & Close Button
    draw_gear_icon(draw, bx1 + 45, by1 + 40, radius=16, fill=0, bg_color=255)
    draw.text((bx1 + 72, by1 + 24), "QUICK SETTINGS", font=FONT_TITLE, fill=0)

    # [ CLOSE ] Button: [1260, by1 + 16, 1415, by1 + 66]
    draw.rectangle([1260, by1 + 16, 1415, by1 + 66], fill=255, outline=0, width=3)
    draw.rectangle([1263, by1 + 19, 1412, by1 + 63], outline=0, width=1)
    draw_close_icon(draw, 1285, by1 + 41, size=9, width=3, fill=0)
    draw.text((1304, by1 + 25), "CLOSE", font=FONT_BOLD, fill=0)

    # Divider 1
    draw.line([bx1 + 20, by1 + 76, bx2 - 20, by1 + 76], fill=0, width=3)

    # SECTION 1: FRONTLIGHT BRIGHTNESS
    draw.text((bx1 + 25, by1 + 92), f"FRONTLIGHT BRIGHTNESS: {bri_val} / 24", font=FONT_BOLD, fill=0)

    # [-] Step Button: [800, by1 + 130, 865, by1 + 185]
    draw.rectangle([800, by1 + 130, 865, by1 + 185], fill=255, outline=0, width=3)
    draw.rectangle([803, by1 + 133, 862, by1 + 182], outline=0, width=1)
    draw.text((823, by1 + 133), "-", font=FONT_HERO, fill=0)

    # Slider Track: [885, by1 + 144, 1265, by1 + 172]
    track_w = 380
    draw.rectangle([885, by1 + 144, 885 + track_w, by1 + 172], outline=0, width=3)
    fill_w = int((track_w - 6) * (bri_val / 24.0))
    if fill_w > 0:
        draw.rectangle([888, by1 + 147, 888 + fill_w, by1 + 169], fill=0)
    # Thumb Handle
    thumb_cx = 888 + fill_w
    draw.rectangle([thumb_cx - 8, by1 + 134, thumb_cx + 8, by1 + 182], fill=0, outline=0)
    draw.rectangle([thumb_cx - 6, by1 + 136, thumb_cx + 6, by1 + 180], fill=255)

    # [+] Step Button: [1285, by1 + 130, 1350, by1 + 185]
    draw.rectangle([1285, by1 + 130, 1350, by1 + 185], fill=255, outline=0, width=3)
    draw.rectangle([1288, by1 + 133, 1347, by1 + 182], outline=0, width=1)
    draw.text((1305, by1 + 133), "+", font=FONT_HERO, fill=0)

    # Numeric readout:
    draw.text((1365, by1 + 140), f"{bri_val}", font=FONT_BOLD, fill=0)

    # Divider 2
    draw.line([bx1 + 20, by1 + 205, bx2 - 20, by1 + 205], fill=180, width=2)

    # SECTION 2: ROTATE 180° FLIP BUTTON
    # Button: [800, by1 + 225, 1410, by1 + 300]
    draw.rectangle([800, by1 + 225, 1410, by1 + 300], fill=255, outline=0, width=3)
    draw.rectangle([804, by1 + 229, 1406, by1 + 296], outline=0, width=1)
    draw_rotate_icon(draw, 835, by1 + 255, radius=15, width=3, fill=0)
    draw.text((865, by1 + 236), "FLIP SCREEN 180°", font=FONT_TITLE, fill=0)
    draw.text((865, by1 + 270), f"(Current: {cur_rot}° Landscape • Tap to toggle)", font=FONT_SMALL, fill=80)

    # Divider 3
    draw.line([bx1 + 20, by1 + 320, bx2 - 20, by1 + 320], fill=180, width=2)

    # SECTION 3: FORCE REFRESH BUTTON
    # Button: [800, by1 + 340, 1410, by1 + 425]
    draw.rectangle([800, by1 + 340, 1410, by1 + 425], fill=255, outline=0, width=3)
    draw.rectangle([804, by1 + 344, 1406, by1 + 421], outline=0, width=1)
    draw_refresh_icon(draw, 835, by1 + 372, radius=15, width=3, fill=0)
    draw.text((865, by1 + 351), "FORCE REFRESH ALL DATA", font=FONT_TITLE, fill=0)
    draw.text((865, by1 + 390), f"Bypasses cache • Syncs Calendars & Weather (Last: {last_sync})", font=FONT_SMALL, fill=80)

    # Divider 4
    draw.line([bx1 + 20, by1 + 438, bx2 - 20, by1 + 438], fill=180, width=2)

    # SECTION 4: POWER PROFILE / BATTERY MODE
    draw.text((bx1 + 25, by1 + 450), "POWER PROFILE / BATTERY MODE:", font=FONT_BOLD, fill=0)

    p_mode = data.get("power_mode", "saver") if data else "saver"
    if p_mode not in ["normal", "saver", "ultra"]:
        p_mode = "saver"

    # Tab 1: NORMAL [800, by1 + 485, 995, by1 + 555]
    is_norm = (p_mode == "normal")
    draw.rectangle([800, by1 + 485, 995, by1 + 555], fill=0 if is_norm else 255, outline=0, width=3)
    if is_norm:
        draw.rectangle([803, by1 + 488, 992, by1 + 552], outline=255, width=1)
        draw_check_icon(draw, 825, by1 + 510, size=14, width=3, fill=255)
        draw.text((842, by1 + 498), "NORMAL", font=FONT_MODE_TITLE, fill=255)
        draw.text((838, by1 + 526), "1m Real-Time", font=FONT_MODE_SUB, fill=255)
    else:
        draw.text((832, by1 + 498), "NORMAL", font=FONT_MODE_TITLE, fill=0)
        draw.text((828, by1 + 526), "1m Real-Time", font=FONT_MODE_SUB, fill=100)

    # Tab 2: BATTERY SAVER [1005, by1 + 485, 1205, by1 + 555]
    is_sav = (p_mode == "saver")
    draw.rectangle([1005, by1 + 485, 1205, by1 + 555], fill=0 if is_sav else 255, outline=0, width=3)
    if is_sav:
        draw.rectangle([1008, by1 + 488, 1202, by1 + 552], outline=255, width=1)
        draw_check_icon(draw, 1025, by1 + 510, size=14, width=3, fill=255)
        draw.text((1042, by1 + 498), "BATTERY SAVER", font=FONT_MODE_TITLE, fill=255)
        draw.text((1048, by1 + 526), "5m Eco Sync", font=FONT_MODE_SUB, fill=255)
    else:
        draw.text((1028, by1 + 498), "BATTERY SAVER", font=FONT_MODE_TITLE, fill=0)
        draw.text((1048, by1 + 526), "5m Eco Sync", font=FONT_MODE_SUB, fill=100)

    # Tab 3: ULTRA SAVER [1215, by1 + 485, 1410, by1 + 555]
    is_ult = (p_mode == "ultra")
    draw.rectangle([1215, by1 + 485, 1410, by1 + 555], fill=0 if is_ult else 255, outline=0, width=3)
    if is_ult:
        draw.rectangle([1218, by1 + 488, 1407, by1 + 552], outline=255, width=1)
        draw_check_icon(draw, 1235, by1 + 510, size=14, width=3, fill=255)
        draw.text((1252, by1 + 498), "ULTRA SAVER", font=FONT_MODE_TITLE, fill=255)
        draw.text((1252, by1 + 526), "Smart Detect", font=FONT_MODE_SUB, fill=255)
    else:
        draw.text((1242, by1 + 498), "ULTRA SAVER", font=FONT_MODE_TITLE, fill=0)
        draw.text((1252, by1 + 526), "Smart Detect", font=FONT_MODE_SUB, fill=100)

    # Subtext explanation of active mode
    if is_norm:
        draw.text((bx1 + 25, by1 + 572), "NORMAL: Original 1m sync • Live clock • Full Wi-Fi activity", font=FONT_SMALL, fill=80)
    elif is_sav:
        draw.text((bx1 + 25, by1 + 572), "BATTERY SAVER: 5m sync • Eco sleep • Night mode • Consistent on battery", font=FONT_SMALL, fill=80)
    else:
        draw.text((bx1 + 25, by1 + 572), "ULTRA SAVER: 15m sync on battery • Smart plug-detect (1m charging)", font=FONT_SMALL, fill=80)

def render_tab_overview(data=None):
    """Tab 0: Overview Screen with Large-Font Today's Agenda (Quick Actions Removed)"""
    w, h = 1448, 1072
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw_header_and_tabs(draw, active_tab=0, header_data=data)

    mid_x = w // 2
    draw.line([mid_x, 175, mid_x, h - 10], fill=0, width=3)

    # --- LEFT SIDE: TODAY'S SCHEDULE (LARGE & READABLE) ---
    draw.text((40, 205), "TODAY'S SCHEDULE", font=FONT_HERO, fill=0)

    # Tactile Refresh Button on Overview
    draw.rectangle([mid_x - 220, 202, mid_x - 40, 258], fill=255, outline=0, width=3)
    draw.rectangle([mid_x - 216, 206, mid_x - 44, 254], outline=0, width=1)
    draw_refresh_icon(draw, mid_x - 192, 230, radius=12, width=3, fill=0)
    draw.text((mid_x - 170, 214), "REFRESH", font=FONT_BOLD, fill=0)

    draw.line([40, 268, mid_x - 40, 268], fill=0, width=3)

    last_sync = data.get("calendar_data", {}).get("last_synced", "Just now") if data else "Just now"
    draw.text((42, 276), f"Last Synced: {last_sync} • Tap REFRESH to update", font=FONT_SMALL, fill=80)

    today_events = data.get("today_events", []) if data else []
    cal_data = data.get("calendar_data", {}) if data else {}
    next_ev = cal_data.get("next_event", None)

    if today_events:
        for i, ev in enumerate(today_events[:5]):
            y = 310 + i * 135
            # Time badge
            draw.rectangle([40, y, 190, y + 48], fill=0, outline=0)
            draw.text((50, y + 8), ev.get("time", "All Day"), font=FONT_MONO_BOLD, fill=255)
            # Calendar tag
            draw.text((210, y + 10), f"[{ev.get('cal', 'Personal')}]", font=FONT_MED, fill=0)
            # Large event title
            title_text = ev.get("title", "")
            if len(title_text) > 30:
                title_text = title_text[:28] + "..."
            draw.text((40, y + 60), title_text, font=FONT_HERO, fill=0)
            draw.line([40, y + 120, mid_x - 40, y + 120], fill=180, width=2)
    else:
        # Big clean callout when today is clear
        card_box = [45, 320, mid_x - 45, 780]
        draw.rectangle(card_box, outline=0, width=4)
        draw.rectangle([card_box[0] + 6, card_box[1] + 6, card_box[2] - 6, card_box[3] - 6], outline=0, width=1)

        draw.text((75, 355), "NO EVENTS TODAY", font=FONT_HERO, fill=0)
        draw.text((75, 415), "Your calendar is completely clear today.", font=FONT_TITLE, fill=0)
        draw.line([75, 475, mid_x - 75, 475], fill=0, width=2)

        if next_ev:
            draw.text((75, 505), "NEXT UPCOMING EVENT:", font=FONT_BOLD, fill=0)
            day_str = next_ev.get("day_label", "")
            t_str = next_ev.get("time", "")
            time_display = f"{day_str} ({t_str})" if t_str != "All Day" else day_str
            draw.text((75, 550), time_display, font=FONT_TITLE, fill=0)
            draw.text((75, 605), next_ev.get("title", ""), font=FONT_HERO, fill=0)
            draw.text((75, 670), f"Calendar: [{next_ev.get('cal', 'Personal')}]", font=FONT_MED, fill=0)

        draw.text((75, 730), "• Tap [ CALENDAR ] tab above for full week schedule", font=FONT_SMALL, fill=0)

    # --- RIGHT SIDE: WEATHER & FORECAST ---
    rx = mid_x + 40
    loc_name = data.get("location_name", "Forecast") if data else "Forecast"
    draw.text((rx, 205), f"WEATHER & FORECAST ({loc_name})", font=FONT_TITLE, fill=0)
    draw.line([rx, 265, w - 40, 265], fill=0, width=3)

    temp_now = data.get("weather_temp", "6°C Clear") if data else "6°C Clear"
    high_low = data.get("weather_range", "High 7° / Low 0°") if data else "High 7° / Low 0°"
    draw.text((rx, 290), temp_now, font=FONT_TITLE, fill=0)
    draw.text((rx, 350), high_low, font=FONT_BOLD, fill=0)

    # Hourly Forecast Blocks
    hourly = data.get("hourly", [("18:00", "5°C", "Clear"), ("21:00", "3°C", "Clear"), ("00:00", "2°C", "Cloud")]) if data else [("18:00", "5°C", "Clear"), ("21:00", "3°C", "Clear"), ("00:00", "2°C", "Cloud")]
    for j, (h_time, h_temp, h_cond) in enumerate(hourly[:3]):
        bx = rx + j * 190
        draw.rectangle([bx, 420, bx + 170, 530], outline=0, width=3)
        draw.text((bx + 20, 435), h_time, font=FONT_BOLD, fill=0)
        draw.text((bx + 20, 470), h_temp, font=FONT_MED, fill=0)
        draw.text((bx + 20, 498), h_cond, font=FONT_SMALL, fill=0)

    # Right Bottom: CLAUDE CODE QUOTA SNAPSHOT
    draw.text((rx, 650), "CLAUDE CODE QUOTA", font=FONT_TITLE, fill=0)
    draw.line([rx, 700, w - 40, 700], fill=0, width=3)

    claude = data.get("claude", {}) if data else {}
    claude_pct = claude.get("percent", 88)
    reset_str = claude.get("reset_str", "Resets in: 2h 00m")
    proj_str = claude.get("tokens_str", "Active Project: None")

    draw.text((rx, 735), "7-Day Usage:", font=FONT_BOLD, fill=0)
    draw_progress_bar(draw, rx + 180, 735, 340, 36, claude_pct, "Used")
    draw.text((rx, 805), f"• {reset_str}", font=FONT_BOLD, fill=0)
    draw.text((rx, 855), f"• {proj_str}", font=FONT_MED, fill=0)

    return img

def render_tab_calendar(data=None):
    """Tab 1: Dedicated Detailed Calendar View (Grouped by Day)"""
    w, h = 1448, 1072
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw_header_and_tabs(draw, active_tab=1, header_data=data)

    mid_x = w // 2
    draw.line([mid_x, 175, mid_x, h - 10], fill=0, width=3)

    cal_data = data.get("calendar_data", {}) if data else {}
    up_7d = cal_data.get("upcoming_7d", [])
    later_m = cal_data.get("later_month", [])
    synced = cal_data.get("synced_stats", [])

    # LEFT COLUMN: NEXT 7 DAYS (GROUPED BY DAY)
    draw.text((40, 205), "UPCOMING (NEXT 7 DAYS)", font=FONT_TITLE, fill=0)

    # Tactile Refresh Button on Calendar Tab
    draw.rectangle([mid_x - 220, 200, mid_x - 40, 255], fill=255, outline=0, width=3)
    draw.rectangle([mid_x - 216, 204, mid_x - 44, 251], outline=0, width=1)
    draw_refresh_icon(draw, mid_x - 192, 227, radius=12, width=3, fill=0)
    draw.text((mid_x - 170, 212), "REFRESH", font=FONT_BOLD, fill=0)

    draw.line([40, 260, mid_x - 40, 260], fill=0, width=3)

    last_sync = cal_data.get("last_synced", "Just now")
    draw.text((42, 268), f"Last Synced: {last_sync} • Tap REFRESH to update", font=FONT_SMALL, fill=80)

    # Group events by day_label
    grouped_7d = OrderedDict()
    for ev in up_7d:
        day = ev.get("day_label", "")
        if day not in grouped_7d:
            grouped_7d[day] = []
        grouped_7d[day].append(ev)

    total_7d_evs = len(up_7d)

    if grouped_7d:
        cur_y = 295
        max_y = h - 25
        for day, evs in grouped_7d.items():
            if cur_y + 44 > max_y:
                break
            # Distinct Day Header Banner (Black with crisp white bold text)
            draw.rectangle([40, cur_y, mid_x - 40, cur_y + 42], fill=0, outline=0)
            day_text = f"{day.upper()}   •   {len(evs)} EVENT{'S' if len(evs)>1 else ''}"
            draw.text((55, cur_y + 7), day_text, font=FONT_BOLD, fill=255)
            cur_y += 52

            for ev in evs:
                if cur_y + 50 > max_y:
                    break

                if total_7d_evs <= 6:
                    # Spacious 2-tier card layout with large 34pt title
                    # Row 1: Time badge + Calendar tag
                    draw.rectangle([45, cur_y, 165, cur_y + 36], fill=0, outline=0)
                    draw.text((55, cur_y + 4), ev.get("time", "All Day"), font=FONT_BOLD, fill=255)

                    cal_name = ev.get("cal", "Personal")
                    tag_w = len(cal_name) * 15 + 24
                    draw.rectangle([175, cur_y, 175 + tag_w, cur_y + 36], fill=255, outline=0, width=2)
                    draw.text((187, cur_y + 4), cal_name, font=FONT_BOLD, fill=0)

                    # Row 2: Event Title (Large, bold, full width)
                    title = ev.get("title", "")
                    if len(title) > 36:
                        title = title[:34] + "..."
                    draw.text((45, cur_y + 44), title, font=FONT_TITLE, fill=0)
                    draw.line([45, cur_y + 88, mid_x - 45, cur_y + 88], fill=210, width=1)
                    cur_y += 98
                else:
                    # Single-tier compact layout with 28pt bold fonts
                    draw.rectangle([45, cur_y, 165, cur_y + 40], fill=255, outline=0, width=2)
                    draw.text((53, cur_y + 6), ev.get("time", "All Day"), font=FONT_BOLD, fill=0)
                    cal_tag = f"[{ev.get('cal', 'Personal')}]"
                    draw.text((178, cur_y + 6), cal_tag, font=FONT_BOLD, fill=0)
                    title = ev.get("title", "")
                    if len(title) > 26:
                        title = title[:24] + "..."
                    draw.text((290, cur_y + 6), title, font=FONT_BOLD, fill=0)
                    draw.line([45, cur_y + 46, mid_x - 45, cur_y + 46], fill=210, width=1)
                    cur_y += 56
            cur_y += 10
    else:
        draw.text((40, 310), "No events scheduled in the next 7 days.", font=FONT_TITLE, fill=0)

    # RIGHT COLUMN: LATER THIS MONTH (GROUPED BY DAY)
    rx = mid_x + 40
    draw.text((rx, 205), "LATER THIS MONTH", font=FONT_TITLE, fill=0)
    draw.line([rx, 260, w - 40, 260], fill=0, width=3)

    grouped_later = OrderedDict()
    for ev in later_m:
        day = ev.get("day_label", "")
        if day not in grouped_later:
            grouped_later[day] = []
        grouped_later[day].append(ev)

    if grouped_later:
        cur_ry = 285
        max_ry = 690
        for day, evs in grouped_later.items():
            if cur_ry + 38 > max_ry:
                break
            # Distinct Day Sub-header
            draw.rectangle([rx, cur_ry, w - 40, cur_ry + 38], fill=235, outline=0, width=2)
            draw.text((rx + 15, cur_ry + 6), f"{day.upper()}", font=FONT_BOLD, fill=0)
            cur_ry += 46
            for ev in evs:
                if cur_ry + 48 > max_ry:
                    break
                t_str = ev.get("time", "All Day")
                c_str = f"[{ev.get('cal', 'Personal')}]"
                title = ev.get("title", "")
                if len(title) > 30:
                    title = title[:28] + "..."
                draw.text((rx + 15, cur_ry + 4), f"{t_str}  {c_str}", font=FONT_BOLD, fill=0)
                draw.text((rx + 15, cur_ry + 36), title, font=FONT_TITLE, fill=0)
                draw.line([rx + 15, cur_ry + 74, w - 40, cur_ry + 74], fill=210, width=1)
                cur_ry += 82
            cur_ry += 8
    else:
        draw.text((rx, 310), "No further events this month.", font=FONT_TITLE, fill=0)

    # BOTTOM RIGHT BOX: CONNECTED CALENDARS
    box_y = 710
    draw.line([rx, box_y - 15, w - 40, box_y - 15], fill=0, width=3)
    draw.text((rx, box_y), "CONNECTED CALENDARS", font=FONT_TITLE, fill=0)

    for c_idx, cs in enumerate(synced[:3]):
        cy = box_y + 48 + c_idx * 44
        draw_check_icon(draw, rx + 25, cy + 14, size=16, width=3, fill=0)
        cal_name = cs.get("name", "Personal")
        cal_cnt = cs.get("count", 0)
        draw.text((rx + 48, cy), f"{cal_name}: {cal_cnt} events synced (Live)", font=FONT_BOLD, fill=0)

    draw.text((rx + 20, box_y + 145), f"• Last Synced: {last_sync} (Live)", font=FONT_MED, fill=0)
    draw.text((rx + 20, box_y + 185), "• To add more calendars (Work, Family), add URLs to config.json", font=FONT_SMALL, fill=0)

    return img

def render_tab_aidev(data=None):
    """Tab 2: AI & Dev Status Screen (Claude Code, System Health, Repo PRs)"""
    w, h = 1448, 1072
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw_header_and_tabs(draw, active_tab=2, header_data=data)

    mid_x = w // 2
    draw.line([mid_x, 175, mid_x, 620], fill=0, width=3)

    # TOP LEFT: CLAUDE CODE
    claude = data.get("claude", {}) if data else {}
    claude_pct = claude.get("percent", 88)
    reset_str = claude.get("reset_str", "Resets in: 2h 00m")
    tokens_str = claude.get("tokens_str", "Active Project: None")
    session_str = claude.get("session_str", "Session: IDLE")

    draw.text((40, 205), "CLAUDE CODE (Sonnet / Opus)", font=FONT_TITLE, fill=0)
    draw.line([40, 255, mid_x - 40, 255], fill=0, width=3)
    draw_progress_bar(draw, 40, 280, 420, 45, claude_pct, "Used")
    draw.text((40, 360), reset_str, font=FONT_BOLD, fill=0)
    draw.text((40, 410), tokens_str, font=FONT_BOLD, fill=0)
    draw.text((40, 460), session_str, font=FONT_MED, fill=0)

    # TOP RIGHT: SYSTEM & NETWORK HEALTH
    sys_h = data.get("sys_health", {}) if data else {}
    rx = mid_x + 40
    draw.text((rx, 205), "SYSTEM & NETWORK HEALTH", font=FONT_TITLE, fill=0)
    draw.line([rx, 255, w - 40, 255], fill=0, width=3)
    draw.text((rx, 285), sys_h.get("host_ip", "Server: Online"), font=FONT_BOLD, fill=0)
    draw.text((rx, 345), sys_h.get("load", "Load Avg: 0.42, 0.55"), font=FONT_BOLD, fill=0)
    draw.text((rx, 405), sys_h.get("kindle_conn", "Kindle: Connected (SSH Wi-Fi)"), font=FONT_BOLD, fill=0)
    draw.text((rx, 465), sys_h.get("status", "System Status: HEALTHY [ OK ]"), font=FONT_MED, fill=0)

    # BOTTOM HALF: REPO & CI STATUS
    repo = data.get("repo", {}) if data else {}
    prs_str = repo.get("prs", "Open PRs: 0 (All caught up)")
    ci_str = repo.get("ci", "CI Pipeline: PASSING [ OK ]")
    sync_str = repo.get("last_sync", "Last Git Sync: Just now")

    draw.line([10, 620, w - 10, 620], fill=0, width=4)
    draw.text((40, 650), "REPO & CI PIPELINE STATUS", font=FONT_TITLE, fill=0)
    draw.line([40, 700, w - 40, 700], fill=0, width=3)

    draw.text((60, 740), prs_str if prs_str.startswith("•") else f"• {prs_str}", font=FONT_BOLD, fill=0)
    draw.text((60, 810), ci_str if ci_str.startswith("•") else f"• {ci_str}", font=FONT_BOLD, fill=0)
    draw.text((60, 880), sync_str if sync_str.startswith("•") else f"• {sync_str}", font=FONT_MED, fill=0)

    return img

def render_tab_smarthome(data=None):
    """
    Tab 3: Smart Home 6-Tile Grid (Real SmartThings Devices)
    RULE: Black background = OFF, White background = ON.
    """
    w, h = 1448, 1072
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw_header_and_tabs(draw, active_tab=3, header_data=data)

    smart = data.get("smart", {}) if data else {}
    lr_tv = smart.get("livingroom_tv", {"switch": "OFF", "active": False, "volume": 6})
    br_tv = smart.get("bedroom_tv", {"switch": "ON", "active": True, "volume": 17})
    mon = smart.get("office_monitor", {"switch": "ON", "active": True, "volume": 31})
    plug = smart.get("smart_plug", {"switch": "ON", "active": True})
    light = smart.get("light_1", {"switch": "ON", "active": True})
    lobby = smart.get("lobby", {"switch": "ON", "active": True})

    tiles = [
        {"title": "LIVINGROOM TV", "lines": [f"POWER: {lr_tv['switch']}", f"Vol: {lr_tv.get('volume', 6)} (Tap power)"], "is_on": lr_tv["active"]},
        {"title": "BEDROOM TV", "lines": [f"POWER: {br_tv['switch']}", f"Vol: {br_tv.get('volume', 17)} (Tap power)"], "is_on": br_tv["active"]},
        {"title": "OFFICE MONITOR", "lines": [f"POWER: {mon['switch']}", f"Vol: {mon.get('volume', 31)} (Tap power)"], "is_on": mon["active"]},
        {"title": "SMART PLUG", "lines": [f"STATE: {plug['switch']}", "(Tapo TV Outlet)"], "is_on": plug["active"]},
        {"title": "LIGHT 1", "lines": [f"STATE: {light['switch']}", "(Tap to toggle)"], "is_on": light["active"]},
        {"title": "LOBBY", "lines": [f"STATE: {lobby['switch']}", "(Tap to toggle)"], "is_on": lobby["active"]},
    ]

    tile_w = 420
    tile_h = 360
    gap_x = 45
    gap_y = 50
    start_x = 45
    start_y = 220

    for idx, t in enumerate(tiles):
        row = idx // 3
        col = idx % 3
        x1 = start_x + col * (tile_w + gap_x)
        y1 = start_y + row * (tile_h + gap_y)
        draw_toggle_tile(draw, [x1, y1, x1 + tile_w, y1 + tile_h], t["title"], t["lines"], is_on=t["is_on"])

    return img

def render_tab_tvremote(data=None):
    """
    Tab 4: TV Remote Control (Livingroom TV via SmartThings)
    RULE: Black background = OFF, White background = ON for TV Power button.
    """
    w, h = 1448, 1072
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    draw_header_and_tabs(draw, active_tab=4, header_data=data)

    smart = data.get("smart", {}) if data else {}
    tv = smart.get("livingroom_tv", {"switch": "OFF", "active": False, "volume": 6, "muted": True})

    mid_x = 650
    draw.line([mid_x, 175, mid_x, h - 10], fill=0, width=3)

    # LEFT COLUMN: POWER & INPUTS, VOLUME
    draw.text((40, 205), "POWER & INPUT (Livingroom)", font=FONT_TITLE, fill=0)
    draw.line([40, 255, mid_x - 40, 255], fill=0, width=3)

    is_tv_on = tv.get("active", False)
    # Power Button using toggle rule (Black = OFF, White = ON)
    draw_toggle_tile(draw, [40, 280, 580, 390], "LIVINGROOM TV POWER", [f"Status: {tv.get('switch', 'OFF')} (Tap to toggle)"], is_on=is_tv_on)

    # Standard buttons for Inputs & Volume
    def draw_std_btn(bbox, lines):
        bx1, by1, bx2, by2 = bbox
        draw.rectangle([bx1, by1, bx2, by2], fill=255, outline=0, width=4)
        draw.rectangle([bx1 + 4, by1 + 4, bx2 - 4, by2 - 4], outline=0, width=1)
        bcy = (by1 + by2) // 2
        if len(lines) == 1:
            draw.text((bx1 + 20, bcy - 14), lines[0], font=FONT_BOLD, fill=0)
        elif len(lines) >= 2:
            draw.text((bx1 + 20, bcy - 24), lines[0], font=FONT_BOLD, fill=0)
            draw.text((bx1 + 20, bcy + 6), lines[1], font=FONT_MED, fill=0)

    draw_std_btn([40, 420, 290, 520], ["HDMI 1", "Input"])
    draw_std_btn([330, 420, 580, 520], ["HDMI 2", "Input"])

    draw.text((40, 570), "VOLUME & AUDIO", font=FONT_TITLE, fill=0)
    draw.line([40, 620, mid_x - 40, 620], fill=0, width=3)

    vol = tv.get("volume", 6)
    draw_std_btn([40, 650, 290, 770], ["VOL +", f"Current: {vol}"])
    draw_std_btn([330, 650, 580, 770], ["PLAY / PAUSE", "Toggle"])

    draw_std_btn([40, 800, 290, 920], ["VOL -", "Lower Vol"])
    draw_std_btn([330, 800, 580, 920], ["MUTE", "Muted" if tv.get("muted") else "Unmuted"])

    # RIGHT COLUMN: D-PAD & NAVIGATION
    rx = mid_x + 40
    draw.text((rx, 205), "NAVIGATION D-PAD", font=FONT_TITLE, fill=0)
    draw.line([rx, 255, w - 40, 255], fill=0, width=3)

    dpad_cx = rx + 360
    dpad_cy = 500

    # DPAD Buttons
    draw_std_btn([dpad_cx - 80, dpad_cy - 200, dpad_cx + 80, dpad_cy - 70], [])
    draw_triangle(draw, dpad_cx, dpad_cy - 135, size=20, direction='up', fill=0)

    draw_std_btn([dpad_cx - 210, dpad_cy - 55, dpad_cx - 80, dpad_cy + 75], [])
    draw_triangle(draw, dpad_cx - 145, dpad_cy + 10, size=20, direction='left', fill=0)

    draw_std_btn([dpad_cx - 70, dpad_cy - 55, dpad_cx + 70, dpad_cy + 75], [" OK"])

    draw_std_btn([dpad_cx + 80, dpad_cy - 55, dpad_cx + 210, dpad_cy + 75], [])
    draw_triangle(draw, dpad_cx + 145, dpad_cy + 10, size=20, direction='right', fill=0)

    draw_std_btn([dpad_cx - 80, dpad_cy + 90, dpad_cx + 80, dpad_cy + 220], [])
    draw_triangle(draw, dpad_cx, dpad_cy + 155, size=20, direction='down', fill=0)

    # Bottom Home & Back
    draw_std_btn([rx + 80, 800, rx + 330, 920], ["BACK", "Return"])
    draw_std_btn([rx + 390, 800, rx + 640, 920], ["HOME", "Smart Hub"])

    return img

def render_tab(tab_idx, data=None):
    """Render a tab by index (0-4), overlaying quick settings dropdown if active."""
    if tab_idx == 0:
        im = render_tab_overview(data)
    elif tab_idx == 1:
        im = render_tab_calendar(data)
    elif tab_idx == 2:
        im = render_tab_aidev(data)
    elif tab_idx == 3:
        im = render_tab_smarthome(data)
    elif tab_idx == 4:
        im = render_tab_tvremote(data)
    else:
        im = render_tab_overview(data)

    if data and data.get("show_settings", False):
        draw = ImageDraw.Draw(im)
        draw_settings_dropdown(draw, data)

    return im

def generate_all_screens(data=None, out_dir=None, rotation=None):
    """Generate all 5 tab screens in rotated Kindle format."""
    if not out_dir:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screens")
    os.makedirs(out_dir, exist_ok=True)

    if rotation is None:
        try:
            cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            with open(cfg_file) as f:
                cfg = json.load(f)
            rotation = cfg.get("kindle", {}).get("rotation", 270)
        except Exception:
            rotation = 270

    for i in range(5):
        im = render_tab(i, data)
        im.save(f"{out_dir}/tab{i}.png")
        im.rotate(rotation, expand=True).save(f"{out_dir}/kindle_tab{i}.png")
