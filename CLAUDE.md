# Cold Calls — CLAUDE.md

## What Is This

**Cold Calls** is a participatory art installation for Seattle Design Festival 2026 by Seattle Design Nerds. Two strangers pick up surreal phone handsets on opposite sides of an easel and talk to each other. Thermal receipt printers prompt them with conversation topics. They "record" responses with stamps, stickers, and tape — no writing utensils. It's framed as fieldwork for the fictional *Seattle Municipal Office of Social Climate*, which contracts six sub-agencies — one per side of each easel.

This repo controls **one easel station** (1 Raspberry Pi 4). Same codebase deploys to all three stations.

## Hardware (per station)

- 1× Raspberry Pi 4 (Raspberry Pi OS, Debian trixie)
- 2× Native Union POP Phone (USB audio — mic + earpiece)
- 2× cradle hook switches (GPIO, mechanical switch, `gpiozero`)
- 2× MHT-80E thermal receipt printers (USB, ESC/POS)
- Each side (phone + printer) on its own USB hub, one hub per USB controller

## Tech Stack

- Python 3.13 (system Python from Pi OS)
- uv (package management)
- arecord/aplay for audio cross-routing (subprocess pipes, pure C hot path)
- pyalsaaudio for mixer control only (volume, AGC)
- python-escpos for MHT-80E printers (all content rendered as images via Pillow)
- gpiozero for cradle switch GPIO
- pytest for testing
- systemd for boot startup

## Current Focus

**Hardening and multi-station deployment.** The core session loop is working end-to-end: hardware discovery, cradle detection (button mode via POP Phone HID), full audio flow (dial tone → DTMF → ring → connecting announcement → cross-route with background music → busy tone), prompt printing via thermal receipts, and ring timeout with not-in-service message. Station 1 (apathy) is the test station. Now deploying to stations 2 and 3.

## Project Structure

```
cold_call/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── setup.sh              # System setup (apt, uv, USB-C host mode, groups)
├── src/cold_call/
│   ├── __init__.py
│   ├── main.py           # Entry point — discovers hardware, runs session loop
│   ├── hardware.py       # USB device discovery, phone+printer pairing
│   ├── session.py        # Session state machine
│   ├── audio.py          # Audio cross-route, sound playback, background music
│   ├── cradle.py         # Cradle switch detection (GPIO, button, keyboard)
│   ├── config.py         # Station config loader (YAML)
│   ├── printer.py        # Receipt printing (prompt dispatches, status receipts)
│   └── prompts.py        # Prompt selection and categories
├── config/               # Per-station YAML configs (station1.yaml, etc.)
├── scripts/              # Manual test scripts
├── assets/
│   ├── fonts/            # Courier Prime (regular + bold)
│   ├── images/           # Generated seal PNGs for receipts
│   ├── audio/            # Sound effects (dial tone, ring, DTMF, announcements)
│   └── prompts/          # Prompt text files by category
├── systemd/              # systemd service + launcher scripts
└── tests/                # pytest tests (sandbox fixture blocks real signals/subprocesses)
```

## What's Working

- **Audio Router** — arecord|aplay cross-route, in-pipeline background music mixer
- **Cradle Detection** — Button mode (POP Phone HID), GPIO mode, keyboard mode
- **Printer Controller** — Raster printing (single-write for DWC2), status receipts on boot
- **Prompt Engine** — 7 department themes, randomized, per-side config
- **Session Manager** — Full state machine: idle → dial tone → DTMF → ring → connect → conversation → hangup
- **Audio Flow** — Dial tone, DTMF, ring, connecting announcement (Piper TTS), busy tone, not-in-service timeout message
- **Boot** — systemd service, hardware wait (3 min), startup banner, status receipts
- **Hardening** — SSH key-only, WiFi power-save off, CPU performance governor, print-before-audio sequencing

## Design Direction

### Session Flow

This is the core loop. Each cycle is one "call" between two strangers.

```
IDLE
  Both phones on hook. Background music silent (or ambient drone).

CALLER_PICKUP (Side A picks up)
  → Play dial tone in Side A earpiece
  → After 1-2s, play DTMF tones simulating dialing a random famous phone number
  → Side B earpiece rings loudly (old telephone ring sound)

WAITING_FOR_ANSWER
  → Side B keeps ringing until pickup or timeout
  → If timeout (~30s), Side A hears "The number you have dialed..." → hang up → IDLE
  → If Side A hangs up first → stop ringing → IDLE

CONNECTING (Side B picks up)
  → Stop ringing
  → Wait ~1 second for person to get phone to ear
  → Play connecting announcement in both earpieces
    (old AT&T style: "Please hold while we connect your call" or similar)
  → Start audio cross-route (Mic A ↔ Earpiece B)
  → Both printers print prompts (different prompt per side)
  → Background music/playlist begins playing mixed into both earpieces

CONVERSATION
  → Cross-route active, background music playing
  → Users talk, share prompts, work on collage
  → Continues until either side hangs up

HANGUP
  → Either side goes on-hook
  → Play hang-up tone / click in the other earpiece
  → Stop cross-route
  → Stop background music
  → Brief cooldown (~5s) before accepting new calls
  → Return to IDLE
```

Either side can be the "caller" — whichever picks up first is Side A for that session. The roles aren't fixed to physical sides.

### Audio Playback

The session flow requires playing sound effects to individual handsets:
- Dial tone, DTMF tones, connecting announcement → caller's earpiece only
- Ring tone → other side's earpiece only
- Background music → both earpieces during conversation
- Hang-up click → remaining earpiece

Use `aplay` to play WAV files to specific ALSA devices (`plughw:N,0`). Sound effects are short WAV files in `assets/audio/`. Background music is a playlist of files that loop during the conversation.

### Robustness
- systemd `Restart=always` (5s restart delay)
- Hardware wait on boot (3-min timeout)
- Graceful printer degradation (one dies, other side keeps working)
- Off-hook busy tone loops until hangup (matches real phone behavior)
- Logging to journalctl

### Cradle Switch Wiring
- Mechanical switch: one terminal → GPIO pin (BCM 17 / BCM 27), other → GND
- gpiozero.Button with internal pull-up + 50ms software debounce
- Off-hook = switch closed = LOW, On-hook = switch open = HIGH
- 3-terminal hook switch: wire the normally-open (NO) pair so circuit closes when phone lifts

### `--no-gpio` Mode
For development without hook switches connected. Keyboard input simulates cradle events:
- Press `A` to toggle Side A on/off hook
- Press `B` to toggle Side B on/off hook
- The cradle module exposes the same interface regardless of mode, so the rest of the code doesn't care

### MHT-80E Printer Notes
- 80mm thermal, USB, ESC/POS command set
- Print area ~72mm (~576px at 203dpi)
- All text rendered as 1-bit images via Pillow for full typographic control
- Images rotated 180° so receipts read correctly when pulled from printer (bottom-up print order)
- python-escpos `File` backend writes to `/dev/usb/lp*`
- User must be in `lp` group for access (setup.sh handles this)

### Prompt Categories (Departments)
| Category | Department |
|---|---|
| apathy | Bureau of Apathy (test only) |
| ambient_belonging | Bureau of Ambient Belonging |
| acceptable_proximity | Office of Acceptable Proximity |
| conditional_invitations | Division of Conditional Invitations |
| deferred_enthusiasm | Commission on Deferred Enthusiasm |
| minimal_engagement | Administration for Minimal Engagement |
| polite_indifference | Department of Polite Indifference |

Stored as plain text files in `assets/prompts/`, one question per line. Each department has a matching seal image in `assets/images/` and metadata in `assets/departments.yaml`.

## Hardware Discovery

`src/cold_call/hardware.py` discovers POP Phones (via ALSA `/sys/class/sound/`) and printers (via `/sys/class/usbmisc/`), then pairs them by USB controller. Each side gets a `Side` object with ALSA card number and printer device path. This is stable regardless of device enumeration order.

Run `uv run python -m cold_call.hardware` to see current topology.

## Audio Architecture

- **arecord|aplay subprocess pipes** for the audio hot path (pure C, no Python in the loop)
- Two pipes: Mic A → Earpiece B, Mic B → Earpiece A
- Python handles: device discovery, mixer setup (volume, AGC), subprocess lifecycle
- USB-C host mode (`dtoverlay=dwc2,dr_mode=host`) gives a second independent USB controller
- Each phone on its own USB controller eliminates Single-TT contention

### Audio Lessons Learned
- PulseAudio module-loopback: POP Phone capture source stalls (latency climbs to 100s+ seconds). Not reliable.
- pyalsaaudio with plughw + threads: intermittent stutter from Python GIL contention. Abandoned.
- **arecord|aplay subprocess pipes: works.** This is the approach.
- **NEVER use ALSA dmix.** DWC2 crackles with dmix — even a single dmix client causes issues. Use `plughw` for all playback. Background music is mixed in-pipeline via a Python mixer subprocess (`arecord | mixer | aplay`), not via dmix. Sound effects (dial tone, ring, busy tone) play via dmix only when the cross-route is NOT running.
- Pi 4 VL805 internal hub is Single-TT — two full-speed USB audio devices on Type-A ports will stutter. Solved by splitting across VL805 + DWC2.
- AB13X USB handset is electrically flaky — causes USB errors under load. Do not use.
- ALSA mixer simple control names: 'PCM', 'Mic', 'Auto Gain Control' (not 'PCM Playback Volume').
- POP Phone default playback volume is very low (30%) — set to 80%+.
- Period 1024 / Buffer 4096 at 48kHz (~21ms/85ms) is a good balance.

## Dev Workflow

```bash
./setup.sh 1          # First time: system deps, uv, USB-C host mode (station 1-3)
uv sync               # Install Python dependencies
uv run pytest         # Run tests
uv run python -m cold_call.hardware   # Check device topology
uv run python scripts/test_crossroute.py   # Test audio cross-route
uv run python scripts/test_printer.py A    # Test printer on side A or B
sudo systemctl status cold-call           # Check service status
sudo journalctl -u cold-call -f           # Follow logs
```

## Principles

- Build incrementally. Get one thing working, then the next.
- Test what matters. Mock hardware in unit tests.
- Keep it simple. This runs unattended at a museum for hours.
- Config over code. No hardcoded device paths — discover at runtime.
