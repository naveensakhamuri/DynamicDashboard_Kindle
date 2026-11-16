#!/bin/bash
# Install SSH public key to Kindle via USB Mass Storage

KEY_SRC="${1:-$HOME/.ssh/id_kindle.pub}"
if [ ! -f "$KEY_SRC" ]; then
  if [ -f "$HOME/.ssh/id_rsa.pub" ]; then
    KEY_SRC="$HOME/.ssh/id_rsa.pub"
  elif [ -f "$HOME/.ssh/id_ed25519.pub" ]; then
    KEY_SRC="$HOME/.ssh/id_ed25519.pub"
  else
    echo "Error: No SSH public key found at $KEY_SRC"
    echo "Generate one first with: ssh-keygen -t rsa -f ~/.ssh/id_kindle"
    exit 1
  fi
fi

PUBKEY=$(cat "$KEY_SRC")
DEST="/Volumes/Kindle/usbnet/etc"

echo "Using SSH public key: $KEY_SRC"
echo "Waiting for Kindle to be plugged in via USB (/Volumes/Kindle)..."
while true; do
  if mount | grep -q ' on /Volumes/Kindle '; then
    if touch "/Volumes/Kindle/.test_write" 2>/dev/null; then
      rm -f "/Volumes/Kindle/.test_write"
      echo "Kindle mounted! Installing SSH public key..."
      mkdir -p "$DEST"
      echo "$PUBKEY" >> "$DEST/authorized_keys"
      sync
      echo "=== SUCCESS: SSH Key installed in $DEST/authorized_keys ==="
      cat "$DEST/authorized_keys"
      sleep 0.5
      diskutil eject /Volumes/Kindle || diskutil unmountDisk /Volumes/Kindle || true
      exit 0
    fi
  fi
  sleep 0.1
done
