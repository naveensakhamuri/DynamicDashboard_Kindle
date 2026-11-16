#!/bin/bash
# Deploy auto-start service and permanent screensaver prevention to Kindle
set -e

# Target Kindle IP and Host Server IP (pass as arguments or set environment variables)
KINDLE_IP="${1:-${KINDLE_IP:-192.168.1.100}}"
HOST_IP="${2:-${KINDLE_HOST_IP:-192.168.1.50}}"
KINDLE_KEY="${KINDLE_SSH_KEY:-${HOME}/.ssh/id_kindle}"

echo "Checking connection to Kindle at $KINDLE_IP..."
if ! ssh -i "$KINDLE_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=3 "root@$KINDLE_IP" "true" >/dev/null 2>&1; then
    echo "[!] Kindle ($KINDLE_IP) is not reachable yet. Please check Wi-Fi or plug in the Kindle."
    echo "    Usage: ./dashboard/deploy_kindle_autostart.sh <KINDLE_IP> <HOST_SERVER_IP>"
    exit 1
fi

echo "[1/4] Remounting root filesystem as read-write..."
ssh -i "$KINDLE_KEY" -o StrictHostKeyChecking=no "root@$KINDLE_IP" "/usr/sbin/mntroot rw 2>/dev/null || mount -o remount,rw /"

echo "[2/4] Uploading updated touch_daemon.sh..."
scp -i "$KINDLE_KEY" -o StrictHostKeyChecking=no dashboard/touch_daemon.sh "root@$KINDLE_IP:/mnt/us/dashboard/touch_daemon.sh"
ssh -i "$KINDLE_KEY" -o StrictHostKeyChecking=no "root@$KINDLE_IP" "chmod +x /mnt/us/dashboard/touch_daemon.sh"

echo "[3/4] Installing Upstart boot service (/etc/init/kindle_dashboard.conf)..."
ssh -i "$KINDLE_KEY" -o StrictHostKeyChecking=no "root@$KINDLE_IP" "cat << EOF > /etc/init/kindle_dashboard.conf
start on started wpa_supplicant
stop on runlevel [06]

respawn
respawn limit 10 5

exec /bin/sh /mnt/us/dashboard/touch_daemon.sh $HOST_IP
EOF"

echo "[4/4] Starting dashboard and disabling native Amazon GUI..."
ssh -i "$KINDLE_KEY" -o StrictHostKeyChecking=no "root@$KINDLE_IP" "
    /usr/sbin/mntroot ro 2>/dev/null || true
    echo saver > /mnt/us/dashboard/power_mode
    touch /mnt/us/usbnet/auto
    killall -9 touch_daemon.sh evtest sleep script 2>/dev/null || true
    /bin/sh /mnt/us/dashboard/touch_daemon.sh $HOST_IP >/dev/null 2>&1 &
"

echo "[✓] Kindle Smart Dashboard configured to auto-start on boot connecting to $HOST_IP!"
