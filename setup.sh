#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y build-essential
sudo apt install -y git python3-pip python3-venv python3-dev libffi-dev

# Audio: PulseAudio, ALSA (dev headers + utils)
sudo apt install -y pulseaudio pulseaudio-utils alsa-utils libasound2-dev

# uv (Python package manager) — installs to ~/.local/bin, adds to PATH via ~/.bashrc
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'Restart your shell or run: source ~/.bashrc'
fi