# Cold Calls

A participatory art installation for **SAM Remix 2026** by [Seattle Design Nerds](https://www.seattledesignnerds.com/).

Two strangers pick up surreal phone handsets on opposite sides of an easel and talk to each other. Thermal receipt printers give them conversation prompts. They "record" responses with stamps, stickers, and tape — no writing utensils. It's framed as an outreach effort from the fictional *Bureau of Ambient Belonging*.

## How It Works

Each easel station runs on a Raspberry Pi 4 with:
- 2 Native Union POP Phone handsets (USB audio)
- 2 MHT-80E thermal receipt printers
- 2 cradle hook switches (GPIO)

The software auto-discovers which phone and printer are paired on each USB hub, cross-routes audio between handsets, and prints conversation prompts.

## Station Setup

### USB Wiring (important!)

The Pi 4's Type-A ports share a single USB controller (VL805) with a Single-TT internal hub. Two full-speed USB audio devices on those ports **will stutter and crackle**. You must split the devices across two controllers:

- **Type-A ports** (VL805 controller): one POP Phone + one printer plugged directly into the onboard ports (no external hub needed)
- **USB-C port** (DWC2 controller): a USB-C hub with the other POP Phone + other printer

The USB-C port is normally for power only. `setup.sh` enables host mode (`dtoverlay=dwc2,dr_mode=host`) so it acts as a second independent USB controller. You'll need a USB-C hub that supports data — not all do. We've had success with **VIA Labs** chipset hubs (e.g. `2109:2817`). Docks that only do DisplayPort/power passthrough won't work. If it shows up as a hub in `lsusb -t`, it works.

Since the USB-C port is used for data, power the Pi through the GPIO header or a PoE hat.

### Prerequisites
- Raspberry Pi 4 running Raspberry Pi OS (Debian trixie)
- 1 USB-C hub with data support (for the second phone + printer pair)
- Each phone + printer pair on its own USB controller

### Install

```bash
git clone <repo-url> ~/cold_call
cd ~/cold_call
./setup.sh
```

`setup.sh` installs system dependencies, enables USB-C host mode, sets up printer permissions, installs uv, and syncs Python packages. A reboot is required after first run (for USB-C host mode and group membership).

### Verify Hardware

After reboot, check that both phones and printers are detected:

```bash
uv run python -m cold_call.hardware
```

You should see two sides paired, each with a phone and printer on the same USB bus.

### Test

```bash
# Audio cross-route (pick up both phones and talk)
uv run python scripts/test_crossroute.py

# Print a test dispatch
uv run python scripts/test_printer.py A
uv run python scripts/test_printer.py B
```

## Development

```bash
uv sync               # Install/update Python dependencies
uv run pytest         # Run tests
```

See [CLAUDE.md](CLAUDE.md) for architecture details, hardware notes, and design direction.
