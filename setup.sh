#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y build-essential
sudo apt install -y git python3-pip python3-venv python3-dev libffi-dev

# Audio: PulseAudio, ALSA (dev headers + utils)
sudo apt install -y pulseaudio pulseaudio-utils alsa-utils libasound2-dev

# CPU governor: prevent latency spikes during audio IRQ handling
# This persists across reboots via /etc/default/cpufrequtils
sudo apt install -y cpufrequtils
echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils >/dev/null
sudo systemctl restart cpufrequtils 2>/dev/null || true

# USB-C host mode: enable DWC2 controller so USB-C port can accept devices
# This gives us a second independent USB bus, avoiding single-TT contention
# between two full-speed USB audio devices on the VL805 controller
BOOT_CONFIG="/boot/firmware/config.txt"
if ! grep -q '^\[all\]' "$BOOT_CONFIG" || ! sed -n '/^\[all\]/,/^\[/p' "$BOOT_CONFIG" | grep -q 'dtoverlay=dwc2,dr_mode=host'; then
    sudo sed -i '/^\[all\]/a dtoverlay=dwc2,dr_mode=host' "$BOOT_CONFIG"
    echo '⚠ Added dwc2 host overlay to config.txt — reboot required'
fi

# uv (Python package manager) — installs to ~/.local/bin, adds to PATH via ~/.bashrc
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'Restart your shell or run: source ~/.bashrc'
fi