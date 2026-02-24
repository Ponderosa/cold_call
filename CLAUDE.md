# Cold Calls — CLAUDE.md

## What Is This

**Cold Calls** is a participatory art installation for SAM Remix 2026 by Seattle Design Nerds. Two strangers pick up surreal phone handsets on opposite sides of an easel and talk to each other. Thermal receipt printers prompt them with conversation topics. They "record" responses with stamps, stickers, and tape — no writing utensils. It's framed as an outreach effort from the fictional *Bureau of Ambient Belonging*.

This repo controls **one easel station** (1 Raspberry Pi 4). Same codebase deploys to all four stations.

## Hardware (per station)

- 1× Raspberry Pi 4 (Raspberry Pi OS, system Python)
- 2× USB phone handsets (USB audio — mic + earpiece)
- 2× cradle hook switches (GPIO, mechanical switch, `gpiozero`)
- 2× MHT-80E thermal receipt printers (USB serial)
- Background music mixed into handset audio

## Tech Stack

- Python 3.13 (system Python from Pi OS, Debian trixie)
- uv (package management)
- pyalsaaudio for audio cross-routing (direct ALSA, no PulseAudio)
- gpiozero for cradle switch GPIO
- pyserial / python-escpos for MHT-80E printers
- pytest for testing
- systemd for boot startup

## Current Focus

**Audio cross-route working.** Mic A → Earpiece B, Mic B → Earpiece A is functional via `scripts/test_crossroute.py` using pyalsaaudio with threaded read/write loops. Waiting on second POP Phone to replace the AB13X (which has flaky USB — corrupt descriptors, bus errors under load).

## Design Direction

These are aspirations, not specs. We'll build toward this incrementally.

### Subsystems (eventual)
- **Audio Router** — Cross-routes handset audio, mixes in background music
- **Cradle Detection** — GPIO reads on hook switches, drives session state
- **Printer Controller** — Drives MHT-80E printers, prints prompts on interval
- **Prompt Engine** — Curated question categories (silly, deep, Seattle, bureaucratic), randomized
- **Session Manager** — State machine: idle → waiting → conversation → wind-down → idle
- **Supervisor** — Watchdog for threads, restart on crash, health checks
- **Background Music** — Ambient audio loop mixed into handsets

### Rough Folder Structure (draft, will evolve)
```
cold_call/
├── CLAUDE.md
├── pyproject.toml
├── src/
│   ├── main.py
│   ├── config.py
│   ├── audio/
│   ├── handset/
│   ├── printer/
│   ├── prompts/
│   └── ...
├── scripts/           # Manual test scripts, monitoring
├── systemd/           # Service files for boot
├── config/            # station.toml per-station config
├── assets/music/
└── tests/
```

### Audio Lessons Learned
- PulseAudio module-loopback: POP Phone capture source stalls (latency climbs to 100s+ seconds). Not reliable.
- Shell pipes (arecord|aplay): Two simultaneous pipes cause crackling from USB bus contention.
- **pyalsaaudio with plughw + threads: works.** One thread per direction, blocking reads, `plughw:` for format conversion. This is the current approach.
- AB13X USB handset is electrically flaky — causes `clear tt error -71`, corrupt descriptors, and USB disconnects under load. Do not use.
- Both USB devices share one 480Mbps bus on the Pi 4 (VL805 controller). Full-speed (12Mbps) devices can cause contention — quality USB devices matter.
- When two identical devices (e.g. two POP Phones) are used, `find_card()` will need to distinguish by USB port path, not just name.

### Robustness Goals
- Each subsystem in its own thread with heartbeat
- Supervisor restarts crashed threads with exponential backoff
- Graceful degradation (one printer dies → other side keeps working)
- USB hotplug tolerance
- systemd `Restart=always` as outer safety net
- Logging to journalctl + rotating file

### Cradle Switch Wiring
- Mechanical switch: one terminal → GPIO pin (BCM 17 / BCM 27), other → GND
- gpiozero.Button with internal pull-up + 50ms software debounce
- On-hook = switch closed = LOW, Off-hook = switch open = HIGH

### MHT-80E Notes
- 80mm thermal, USB serial, ESC/POS command set
- Baud likely 9600 or 115200
- Some units need DTR toggle on connect
- Print area ~72mm

### Prompt Categories
| Category | Tone |
|---|---|
| icebreakers | Warm, easy |
| seattle | Local, knowing |
| silly | Absurd, playful |
| deep | Reflective |
| bureaucratic | Deadpan official |

Stored as plain text files, one question per line.

## Dev Workflow

```bash
uv sync
uv run pytest
uv run python -m cold_call.main
```

## Principles

- Build incrementally. Get one thing working, then the next.
- Test what matters. Mock hardware in unit tests.
- Keep it simple. This runs unattended at a museum for hours.
- Config over code. station.toml for device paths, volumes, timing.