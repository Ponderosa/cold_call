# Cold Calls

A participatory art installation for **SAM Remix 2026** by [Seattle Design Nerds](https://www.seattledesignnerds.com/).

Two strangers pick up surreal phone handsets on opposite sides of an easel and talk to each other. Thermal receipt printers give them conversation prompts. They "record" responses with stamps, stickers, and tape — no writing utensils. It's framed as an outreach effort from the fictional *Bureau of Ambient Belonging*.

## Stations

| Station | Hostname | Config | Departments |
|---------|----------|--------|-------------|
| 1 | coldcall1 | station1.yaml | Minimal Engagement / Deferred Enthusiasm |
| 2 | coldcall2 | station2.yaml | Acceptable Proximity / Ambient Belonging |
| 3 | coldcall3 | station3.yaml | Polite Indifference / Conditional Invitations |

## Hardware (per station)

- 1× Raspberry Pi 4 running Raspberry Pi OS (Debian trixie)
- 2× Native Union POP Phone (USB audio — mic + earpiece)
- 2× MHT-80E thermal receipt printers (USB, ESC/POS)
- 2× cradle hook switches (GPIO or POP Phone button)
- 1× USB-C hub with data support (for the second phone + printer pair)
- Power via GPIO header or PoE hat (USB-C port is used for data)

### USB Wiring

The Pi 4's Type-A ports share a single USB controller (VL805) with a Single-TT internal hub. Two full-speed USB audio devices on those ports **will stutter and crackle**. Split the devices across two controllers:

- **Type-A ports** (VL805): one POP Phone + one printer
- **USB-C port** (DWC2): USB-C hub with the other POP Phone + other printer

`setup.sh` enables USB-C host mode (`dtoverlay=dwc2,dr_mode=host`). You need a USB-C hub that supports data — not all do. Hubs with **VIA Labs** chipsets (e.g. `2109:2817`) work. If it shows up in `lsusb -t`, it works.

## New Station Setup

### 1. Prepare the SD card

- Flash Raspberry Pi OS Lite (Debian trixie, 64-bit) with Raspberry Pi Imager
- In imager settings: set hostname, enable SSH, paste your public SSH key
- Insert SD card, connect all USB hardware, boot the Pi

### 2. Clone and run setup

SSH into the Pi, then:

```bash
git clone https://github.com/ponderosa/cold_call.git ~/workspace/cold_call
cd ~/workspace/cold_call
./setup.sh <station-number>   # 1, 2, or 3
```

`setup.sh` handles everything:
- System packages (build-essential, alsa-utils, etc.)
- CPU governor (performance mode)
- SSH hardening (disables password auth — keys must already work)
- WiFi power-save disable (keeps SSH reachable overnight)
- USB-C host mode (dwc2 overlay)
- User groups (audio, gpio, input, lp)
- uv + Python dependencies
- PulseAudio disable (if present)
- systemd service install + enable

### 3. Reboot

```bash
sudo reboot
```

The first reboot activates USB-C host mode and group membership. The `cold-call` service starts automatically on boot.

### 4. Verify

```bash
# Check service is running
sudo systemctl status cold-call

# Watch logs (should show startup banner + hardware discovery)
sudo journalctl -u cold-call -f

# Both printers should print a status receipt on startup
```

If hardware isn't detected, the service waits up to 3 minutes for USB devices to enumerate before giving up.

### Manual hardware checks

```bash
# Show USB topology and device pairing
uv run python -m cold_call.hardware

# Test audio cross-route
uv run python scripts/test_crossroute.py

# Test individual printer
uv run python scripts/test_printer.py A
uv run python scripts/test_printer.py B
```

## Ongoing Operations

```bash
# Restart the service
sudo systemctl restart cold-call

# Follow logs
sudo journalctl -u cold-call -f

# Pull latest code and restart (works with HTTPS clone)
cd ~/workspace/cold_call && git pull && sudo systemctl restart cold-call

# Update Python deps after pyproject.toml changes
uv sync && sudo systemctl restart cold-call
```

## Development

```bash
uv sync               # Install/update Python dependencies
uv run pytest         # Run tests
```

See [CLAUDE.md](CLAUDE.md) for architecture details, hardware notes, and design direction.
