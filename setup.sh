#!/usr/bin/env bash
set -euo pipefail

# --- Station number argument ---
STATION="${1:-}"
if [[ -z "$STATION" ]]; then
    echo "Usage: ./setup.sh <station-number>"
    echo "  station-number: 1, 2, or 3"
    exit 1
fi
if [[ ! "$STATION" =~ ^[1-3]$ ]]; then
    echo "ERROR: Station number must be 1, 2, or 3 (got: $STATION)"
    exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- System packages ---
sudo apt update
sudo apt install -y build-essential
sudo apt install -y git python3-pip python3-venv python3-dev libffi-dev
sudo apt install -y alsa-utils libasound2-dev

# CPU governor: prevent latency spikes during audio IRQ handling
if command -v cpufreq-set &>/dev/null; then
    echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils >/dev/null
    sudo systemctl restart cpufrequtils 2>/dev/null || true
else
    # cpufrequtils not available on trixie — set governor directly
    for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor; do
        echo performance | sudo tee "$cpu" >/dev/null 2>&1 || true
    done
    echo '>>> CPU governor set to performance'
fi

# --- USB-C host mode ---
BOOT_CONFIG="/boot/firmware/config.txt"
if ! grep -q '^\[all\]' "$BOOT_CONFIG" || ! sed -n '/^\[all\]/,/^\[/p' "$BOOT_CONFIG" | grep -q 'dtoverlay=dwc2,dr_mode=host'; then
    sudo sed -i '/^\[all\]/a dtoverlay=dwc2,dr_mode=host' "$BOOT_CONFIG"
    echo '>>> Added dwc2 host overlay to config.txt — reboot required'
fi

# --- Printer: add user to lp group ---
if ! groups "$USER" | grep -q '\blp\b'; then
    sudo usermod -aG lp "$USER"
    echo '>>> Added user to lp group'
fi

# --- Input devices: add user to input group (for POP Phone HID buttons) ---
if ! groups "$USER" | grep -q '\binput\b'; then
    sudo usermod -aG input "$USER"
    echo '>>> Added user to input group'
fi

# --- Audio group (for direct ALSA access) ---
if ! groups "$USER" | grep -q '\baudio\b'; then
    sudo usermod -aG audio "$USER"
    echo '>>> Added user to audio group'
fi

# --- GPIO group (for cradle switch access) ---
if ! groups "$USER" | grep -q '\bgpio\b'; then
    sudo usermod -aG gpio "$USER" 2>/dev/null || true
    echo '>>> Added user to gpio group'
fi

# --- uv (Python package manager) ---
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# --- Python dependencies ---
cd "$REPO_DIR"
uv sync

# --- Disable PulseAudio (if installed) ---
# PulseAudio grabs ALSA devices exclusively, blocking our direct
# arecord/aplay access via plughw. Not present on Lite images.
if command -v pulseaudio &>/dev/null; then
    systemctl --user stop pulseaudio.service pulseaudio.socket 2>/dev/null || true
    systemctl --user disable pulseaudio.service pulseaudio.socket 2>/dev/null || true
    systemctl --user mask pulseaudio.service pulseaudio.socket
    PULSE_CLIENT_CONF="/etc/pulse/client.conf"
    if ! grep -q '^autospawn = no' "$PULSE_CLIENT_CONF" 2>/dev/null; then
        echo 'autospawn = no' | sudo tee -a "$PULSE_CLIENT_CONF" >/dev/null
    fi
    echo '>>> PulseAudio disabled'
else
    echo '>>> PulseAudio not installed (OK for Lite)'
fi

# --- Persist station identity ---
echo "$STATION" | sudo tee /etc/cold-call-station >/dev/null
echo ">>> Station set to: $STATION"

if [[ ! -f "$REPO_DIR/config/station${STATION}.yaml" ]]; then
    echo "WARNING: config/station${STATION}.yaml does not exist!"
fi

# --- Install and enable systemd service ---
chmod +x "$REPO_DIR/systemd/run-station.sh" "$REPO_DIR/systemd/start-station.sh" "$REPO_DIR/systemd/stop-station.sh"
sudo ln -sf "$REPO_DIR/systemd/cold-call.service" /etc/systemd/system/cold-call.service
sudo systemctl daemon-reload
sudo systemctl enable cold-call.service
echo '>>> cold-call.service installed and enabled'

echo ""
echo "=== Setup complete for station $STATION ==="
echo "Reboot to start automatically:"
echo "  sudo reboot"
echo ""
echo "After reboot, check status:"
echo "  sudo systemctl status cold-call"
echo "  sudo journalctl -u cold-call -f"
