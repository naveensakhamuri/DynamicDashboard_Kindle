#!/bin/sh
# Kindle Dashboard Service Manager

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="${PLIST:-$HOME/Library/LaunchAgents/com.antigravity.kindle-dashboard.plist}"
LOG_FILE="$SCRIPT_DIR/server.err"

case "$1" in
    status)
        echo "=== LaunchAgent Status ==="
        launchctl list | grep com.antigravity.kindle-dashboard || echo "Service NOT loaded in launchd"
        echo "\n=== Health Endpoint Check ==="
        curl -s --connect-timeout 2 http://127.0.0.1:8000/health && echo " (Healthy)" || echo " (Unreachable)"
        ;;
    start)
        echo "Starting Kindle Dashboard service..."
        launchctl load "$PLIST"
        sleep 2
        curl -s http://127.0.0.1:8000/health && echo " [Started Successfully]"
        ;;
    stop)
        echo "Stopping Kindle Dashboard service..."
        launchctl unload "$PLIST"
        echo "Stopped."
        ;;
    restart)
        echo "Restarting Kindle Dashboard service..."
        launchctl unload "$PLIST" 2>/dev/null
        sleep 1
        launchctl load "$PLIST"
        sleep 2
        curl -s http://127.0.0.1:8000/health && echo " [Restarted Successfully]"
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {status|start|stop|restart|logs}"
        exit 1
        ;;
esac
