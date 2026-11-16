# DynamicDashboard_Kindle 🚀

Turn an old **Amazon Kindle Paperwhite** (or other e-ink touchscreen Kindle) into an interactive, always-on smart home dashboard and developer desk display with real hardware touch controls and multi-calendar sync!

---

## 🌟 Features

- **5 Interactive Tabs with Real Touch Support**:
  - 🏠 **Tab 0: Home Overview**: Live weather forecast (Open-Meteo, free, no API key needed!), real-time clock & date, large-font Today's Schedule, Kindle battery indicator, and hardware frontlight brightness slider with instant feedback.
  - 📅 **Tab 1: Multi-Calendar**: Timeline agenda syncing multiple Google Calendar / iCal feeds (e.g. Personal + Work), next 7-day upcoming events, monthly agenda, and per-calendar sync status.
  - 💻 **Tab 2: AI & Dev Hub**: Claude Code token quota tracker (resets countdown), active CLI session & project watcher, GitHub PR status via `gh` CLI, host system health (CPU load average, local IP, network status).
  - 💡 **Tab 3: Smart Home**: 6-tile interactive device grid controlling Samsung SmartThings TVs, smart plugs, monitors, and lights with clear visual toggle feedback (Black = OFF, White = ON).
  - 📺 **Tab 4: TV Remote**: Samsung SmartThings TV remote with Power, Volume (+/-), Mute, HDMI 1/2 input switching, full directional D-pad, OK, Home, and Back controls.
- **Dynamic Orientation Switching (90° / 270°)**:
  - Quick Settings drawer orientation toggle button rotates the UI 180° instantly, allowing you to charge your Kindle from the left or right side while on a stand.
- **Interactive Quick Settings Drawer**:
  - Tap the top-right `⚙` gear button on any tab to open the overlay drawer:
    - **Frontlight Brightness**: Real-time hardware slider (0–24 intensity).
    - **180° Screen Flip**: Inverts orientation between 90° and 270°.
    - **Force Refresh**: Instantly bypasses cache and syncs latest calendars and weather.
    - **Power Profile / Battery Mode Selection**:
      - 🟢 **Normal**: 1-minute real-time RTC clock ticker.
      - 🟡 **Battery Saver**: 5-minute clock sync, deep 30-minute sleep at night (11 PM – 7 AM) with frontlight auto-off, Wi-Fi power-management enabled.
      - 🟣 **Ultra Battery Saver**: Smart charging detection — 1-minute ticker when plugged into USB power, 15-minute daytime sync on battery, 60-minute sleep at night.
  - **Header / Clock Tap**: Tapping anywhere on the top clock or weather bar instantly triggers a live refresh.
- **Permanent Kindle Auto-Start on Boot**:
  - Includes `deploy_kindle_autostart.sh` which installs an Upstart service on the Kindle (`/etc/init/kindle_dashboard.conf`), stops native Amazon GUI to prevent screen takeover, and starts `touch_daemon.sh` on device boot.
- **Ultra-Fast E-Ink Touch Interaction**:
  - Uses `evtest` on `/dev/input/event1` to capture hardware touch releases and maps raw portrait coordinates to landscape layout.
  - Switches tabs instantly with partial refresh using `fbink` with fast `A2` waveform mode (<100ms response time).
  - SmartThings API client with cached device polling (15-min TTL) protecting against rate-limits.
  - Direct hardware frontlight brightness adjustment via Kindle `lipc`.
- **Clean & Lightweight Codebase**:
  - Contains only the dashboard server, e-ink renderer, touch daemon, and deployment tooling.
  - Links directly to official community jailbreak repositories and releases without bundling third-party binaries.

---

## 🖥️ Interactive Tab Layouts

```
+--------------------------------------------------------------------------------------------------+
| 04:30 PM FRI, NOV 13   18°C (No Rain)       BRI: [-] [======|   ] [+]   [⟳]   BAT: 85%            |
+---------------+-------------------+-------------------+-------------------+----------------------+
| [ OVERVIEW ]  |   CALENDAR        |    AI & DEV       |   SMART HOME      |    TV REMOTE         |
+---------------+-------------------+-------------------+----------------------+
| TODAY'S SCHEDULE                  | WEATHER & FORECAST (Open-Meteo)                              |
| • 10:00 [Work] Team Standup       | Current: 18°C Clear (High 20° / Low 12°)                     |
| • 14:30 [Work] Architecture Sync  | Hourly: 18:00 (17°)  |  21:00 (15°)  |  00:00 (13°)          |
| • 19:00 [Personal] Dinner         |                                                              |
|                                   | CLAUDE CODE QUOTA                                            |
|                                   | 7-Day Usage: [===================     ] 78% Used             |
| • Tap [CALENDAR] for next 30 days | Resets in: 2h 15m  •  Active Session: IDLE                   |
+-----------------------------------+--------------------------------------------------------------+
```

---

## 📂 Repository Structure

```
DynamicDashboard_Kindle/
├── dashboard/               # Python server, PIL renderer & Kindle scripts
│   ├── server.py            # HTTP event server & Kindle push daemon
│   ├── renderer.py          # 1448x1072 E-Ink UI renderer (Pillow, 5 tabs)
│   ├── data_service.py      # Weather, Multi-Calendar, Claude, GitHub & SmartThings data
│   ├── smartthings.py       # Samsung SmartThings REST API client
│   ├── touch_daemon.sh      # Shell script running on Kindle (maps touch to actions)
│   ├── deploy_kindle_autostart.sh # Installs Upstart auto-start service on Kindle
│   ├── service.sh           # macOS background service manager (start/stop/status)
│   ├── config.example.json  # Configuration template
│   ├── com.antigravity.kindle-dashboard.plist.template # launchd service template
│   └── screens/             # Generated screens cache
├── install_key.sh           # Auto-installs your SSH public key when Kindle mounts
├── requirements.txt         # Python dependencies (Pillow)
├── LICENSE                  # MIT License
└── README.md
```

---

## 📱 Hardware & Compatibility

- **Target Device**: Amazon Kindle Paperwhite 3 (7th Gen / PW3 / 1448x1072).
- **Compatible Devices**:
  - Paperwhite 2, 4, 5 (PW2 / PW4 / PW5)
  - Kindle Oasis 1, 2, 3
  - Kindle Touch, Voyage, Basic Touch
  *(Note: Other resolutions can adjust layout coordinates in `dashboard/renderer.py` and `dashboard/touch_daemon.sh`).*
- **Firmware Support**:
  - **WinterBreak2 (Recommended)**: Firmware `<= 5.16.x` via Experimental Browser & `dialoger.html`
  - **LanguageBreak (Alternative)**: Firmware `<= 5.16.2.1.1` via demo mode

---

## 🔗 Required Third-Party Jailbreak Tools & Downloads

Before setting up the dashboard, download the following standard community jailbreak packages from their official sources:

| Tool | Purpose | Official Download / Reference Link |
| :--- | :--- | :--- |
| **WinterBreak2** | Primary Webkit/Browser Jailbreak (FW $\le$ 5.16.x) | [penguins184.xyz/wb2](https://penguins184.xyz/wb2) • [MobileRead Thread](https://www.mobileread.com/forums/showthread.php?t=356888) |
| **LanguageBreak** | Alternative Demo Mode Jailbreak (FW $\le$ 5.16.2.1.1) | [GitHub: notmarek/LanguageBreak](https://github.com/notmarek/LanguageBreak) • [MobileRead Thread](https://www.mobileread.com/forums/showthread.php?t=351745) |
| **Jailbreak Hotfix** | Survives Amazon OTA updates & keeps jailbreak intact | [NiLuJe's Kindle Hacks Snapshots](https://www.mobileread.com/forums/showthread.php?t=225030) (`JailBreak-*-FW5.x-hotfix.zip`) |
| **MRPI (MobileRead Package Installer)** | Installs `.bin` packages via `;log mrpi` search bar command | [MRPI Release Thread](https://www.mobileread.com/forums/showthread.php?t=251143) (`kual-mrinstaller-*.tar.xz`) |
| **KUAL Booklet** | Kindle Unified Application Launcher application | [KUAL Thread](https://www.mobileread.com/forums/showthread.php?t=203326) / [NiLuJe Snapshots](https://www.mobileread.com/forums/showthread.php?t=225030) (`KUAL-*-booklet.tar.xz`) |
| **USBNetwork Hack** | Passwordless SSH access over Wi-Fi and USB | [USBNetwork Thread](https://www.mobileread.com/forums/showthread.php?t=88004) / [NiLuJe Snapshots](https://www.mobileread.com/forums/showthread.php?t=225030) (`kindle-usbnet-*.tar.xz`) |

---

## 🛠️ Step-by-Step Setup Guide

### Phase 1: Jailbreak Your Kindle (WinterBreak2 - Recommended)

> [!IMPORTANT]
> Remove any lock screen PIN or password from your Kindle before starting. Ensure your Kindle is connected to a stable Wi-Fi network and has battery charged above 50%.

1. **Download WinterBreak2**:
   - Download the payload zip from [penguins184.xyz/wb2](https://penguins184.xyz/wb2) or the [MobileRead Release Thread](https://www.mobileread.com/forums/showthread.php?t=356888).
   - Connect your Kindle via USB mass storage.
   - Extract the downloaded archive and copy the `winterbreak2` directory (containing `dialoger.html`) directly into the root directory of your Kindle drive (`/Volumes/Kindle/winterbreak2`).
   - Safely eject and disconnect your Kindle from USB.

2. **Trigger the Jailbreak via Experimental Browser**:
   - Connect the Kindle to your local Wi-Fi.
   - Open the **Experimental Browser** on your Kindle:
     - Tap the top-right menu button (`⋮`) $\rightarrow$ **Experimental Browser** (or *Settings* $\rightarrow$ *Device Options* $\rightarrow$ *Advanced* $\rightarrow$ *Experimental Browser*).
   - In the browser address bar, navigate to:
     ```text
     https://penguins184.xyz/wb2
     ```
   - Tap the **Jailbreak** button on the webpage.
   - The browser opens the local `winterbreak2/dialoger.html` bridge exploit and automatically executes the `jb.sh` payload in the background.
   - Wait ~30–45 seconds. The Kindle will display jailbreak execution messages and reboot the GUI.
   - Once restarted, a **Jailbroken** document / status on your home screen confirms success!

> [!TIP]
> **Alternative Offline Method (LanguageBreak)**:
> If your Kindle cannot connect to Wi-Fi/browser or is on firmware `<= 5.16.2.1.1` in demo mode, follow the instructions at [notmarek/LanguageBreak](https://github.com/notmarek/LanguageBreak).

---

### Phase 2: Install Essential Packages (Hotfix, KUAL, MRPI, USBNetwork)

From [NiLuJe's Kindle Hacks](https://www.mobileread.com/forums/showthread.php?t=225030) and the links above:

1. **Install Jailbreak Hotfix**:
   - Extract `Update_jailbreak_hotfix_*_install.bin` from `JailBreak-*-FW5.x-hotfix.zip`.
   - Copy it to the root of your Kindle (`/Volumes/Kindle/`).
   - Eject Kindle and tap **Settings** $\rightarrow$ **Update Your Kindle** (or *Settings* $\rightarrow$ *Device Options* $\rightarrow$ *Update Your Kindle*).
2. **Install MRPI & Packages**:
   - Connect Kindle back to USB.
   - Extract `kual-mrinstaller-*.tar.xz`: copy the `extensions/MRInstaller` directory to `/Volumes/Kindle/extensions/MRInstaller`.
   - Create a directory named `mrpackages` on the Kindle root: `/Volumes/Kindle/mrpackages`.
   - Extract `KUAL-*-booklet.tar.xz`: copy `Update_KUALBooklet_*_install.bin` into `/Volumes/Kindle/mrpackages/`.
   - Extract `kindle-usbnet-*.tar.xz`: copy `Update_usbnet_*_install_pw2_and_up.bin` into `/Volumes/Kindle/mrpackages/`.
3. **Trigger Installation via MRPI**:
   - Safely eject your Kindle.
   - In the Kindle search bar, type:
     ```text
     ;log mrpi
     ```
   - Press Enter / Search. MRInstaller will automatically run and install both KUAL and USBNetwork with onscreen e-ink status progress!

---

### Phase 3: Setup Passwordless SSH & Wi-Fi

1. **Install your SSH Public Key**:
   - On your host computer, run the key installation helper:
     ```bash
     chmod +x install_key.sh
     ./install_key.sh ~/.ssh/id_kindle.pub
     ```
   - Plug your Kindle in via USB. The script will automatically detect the Kindle mount, copy your public key to `/Volumes/Kindle/usbnet/etc/authorized_keys`, and safely eject.
2. **Enable SSH over Wi-Fi**:
   - On your Kindle, open **KUAL** -> **USBNetwork** -> **Toggle USBNetwork**.
   - Ensure the Kindle is connected to the same local Wi-Fi network as your host computer.
   - Find your Kindle's IP address (**Settings** -> **Device Options** -> **Device Info** or via router).
3. **Verify SSH Access**:
   ```bash
   ssh -i ~/.ssh/id_kindle root@<KINDLE_IP>
   ```
   *(You should be dropped directly into the Kindle root shell without a password prompt!)*

---

### Phase 4: Deploy the Kindle Touch Daemon & Auto-Start Service

You can deploy the touch daemon either with a single automated script or manually:

#### Option A: One-Command Automated Deployment (Recommended)
Run the auto-start deployment script from your host computer:
```bash
chmod +x dashboard/deploy_kindle_autostart.sh
./dashboard/deploy_kindle_autostart.sh <KINDLE_IP> <HOST_SERVER_IP>
```
This script automatically:
1. Remounts Kindle filesystem as read-write.
2. Uploads `dashboard/touch_daemon.sh` to `/mnt/us/dashboard/`.
3. Installs an Upstart service at `/etc/init/kindle_dashboard.conf` so the dashboard automatically starts on boot.
4. Shuts down the Amazon GUI (`lab126_gui`) to prevent screen conflicts and saves battery.

#### Option B: Manual Deployment
1. SSH into the Kindle and create the dashboard directory:
   ```bash
   ssh -i ~/.ssh/id_kindle root@<KINDLE_IP> "mkdir -p /mnt/us/dashboard"
   ```
2. Copy `dashboard/touch_daemon.sh` to your Kindle:
   ```bash
   scp -i ~/.ssh/id_kindle dashboard/touch_daemon.sh root@<KINDLE_IP>:/mnt/us/dashboard/touch_daemon.sh
   ssh -i ~/.ssh/id_kindle root@<KINDLE_IP> "chmod +x /mnt/us/dashboard/touch_daemon.sh"
   ```
3. Test running the touch listener:
   ```bash
   ssh -i ~/.ssh/id_kindle root@<KINDLE_IP> "/mnt/us/dashboard/touch_daemon.sh <HOST_SERVER_IP>"
   ```
   *Touch the screen; you will see touch coordinates printed in real-time!*

---

### Phase 5: Configure & Start Dashboard Server

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/naveensakhamuri/DynamicDashboard_Kindle.git
   cd DynamicDashboard_Kindle
   ```
2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Create Your Configuration**:
   ```bash
   cp dashboard/config.example.json dashboard/config.json
   ```
4. **Edit `dashboard/config.json`**:
   - `location`: Set your city name, postcode, latitude, and longitude for Open-Meteo weather.
   - `calendars`: Add any number of private iCal calendar feeds (Personal, Work, Family).
   - `smart_home`: Add your Samsung SmartThings Personal Access Token and device UUIDs.
   - `kindle`: Set your Kindle's local Wi-Fi IP, SSH key path, and preferred initial rotation (`90` or `270`).
5. **Start the Server**:
   ```bash
   python3 dashboard/server.py
   ```
   The server will:
   - Generate all 5 screens in `dashboard/screens/`.
   - Push them to your Kindle via `scp`.
   - Display Tab 0 instantly with `fbink`.
   - Start listening on port `8000` for touch, tab switch, and rotation events!

---

## ⚙️ Background Daemon (macOS / Linux)

### On macOS (launchd):
Use the included `service.sh` manager:
```bash
# 1. Copy and customize plist
cp dashboard/com.antigravity.kindle-dashboard.plist.template ~/Library/LaunchAgents/com.antigravity.kindle-dashboard.plist
# Edit paths in ~/Library/LaunchAgents/com.antigravity.kindle-dashboard.plist to match your system

# 2. Manage service
./dashboard/service.sh start
./dashboard/service.sh status
./dashboard/service.sh logs
./dashboard/service.sh stop
```

---

## 💡 How It Works Under the Hood

```
   [ Kindle Paperwhite ]                                 [ Host Computer (Mac / Linux) ]
+----------------------------+                          +-------------------------------+
|  Touch Event (/dev/input)  |                          |                               |
|            |               |                          |    dashboard/server.py        |
|            v               |                          |    (HTTP Server on :8000)     |
|     touch_daemon.sh        |                          |               ^               |
|   (evtest -> coordinate    |                          |               |               |
|    landscape mapping)      |                          |               |               |
|            |               |                          |               |               |
|    +-------+-------+       |                          |               |               |
|    |               |       |                          |               |               |
| Tab Switch    Action Tap   |                          |               |               |
|    |               |       |                          |               |               |
|  fbink             +-------+------ HTTP GET /tap -----> Dispatch to SmartThings / API |
| (Instant local             |                          |               |               |
|  A2 partial                |                          |         data_service          |
|  refresh)                  |<------ scp new screen ---+   (Weather, Cal, AI, System)  |
+----------------------------+                          +-------------------------------+
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to open a PR or Issue to add more widgets (Home Assistant, Spotify, MQTT, transit departure boards, etc.).

---

## 📜 License & Credits

- Exploit packages and tools created by the incredible **MobileRead** community:
  - **NiLuJe** (`fbink`, `USBNetwork`, `MRInstaller`)
  - **notmarek** (`LanguageBreak`)
  - **yparitcher**
- Open-Meteo for the free weather API.
- Licensed under the [MIT License](LICENSE).
