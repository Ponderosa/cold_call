"""Hardware discovery for Cold Calls stations.

Finds POP Phones and MHT-80E printers, pairs them by USB bus so each
"side" (A/B) has one phone + one printer on the same hub.

Discovery uses sysfs paths — stable regardless of enumeration order.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import alsaaudio


@dataclass
class Side:
    """One side of the easel: a phone + printer paired on the same USB bus."""
    label: str           # "A" or "B"
    card: int            # ALSA card number
    card_id: str         # ALSA card id (e.g. "Phone", "Phone_1")
    printer_dev: str     # e.g. "/dev/usb/lp0"
    usb_bus: str         # USB bus prefix for grouping
    input_dev: str | None = None  # e.g. "/dev/input/event0" (POP Phone HID)


def _usb_bus_prefix(sysfs_path: str) -> str:
    """Extract the USB controller prefix from a sysfs device path.

    e.g. '/sys/devices/platform/soc/fe980000.usb/usb3/3-1/...' -> 'fe980000.usb'
         '/sys/devices/platform/scb/fd500000.pcie/.../usb1/1-1/...' -> 'fd500000.pcie'

    This groups devices by which USB controller they're on.
    """
    parts = sysfs_path.split("/")
    # Walk backwards to find the 'usbN' segment, then take the controller before it
    for i, part in enumerate(parts):
        if part.startswith("usb") and part[3:].isdigit():
            # The controller is the component before usbN
            return parts[i - 1]
    return sysfs_path


# Keywords matched against USB manufacturer + product strings to identify phones.
# Any match means the device is a phone. Case-insensitive.
_PHONE_KEYWORDS = ["POP Phone", "JieLi"]


def _find_pop_phones() -> list[dict]:
    """Find phone ALSA cards by keyword search on USB manufacturer/product strings."""
    phones = []
    for card_dir in sorted(Path("/sys/class/sound").glob("card[0-9]*")):
        card_num = int(card_dir.name.removeprefix("card"))
        try:
            card_id = (card_dir / "id").read_text().strip()
        except OSError:
            continue

        device_link = card_dir / "device"
        if not device_link.exists():
            continue
        sysfs_path = str(device_link.resolve())

        # Read USB manufacturer + product strings for keyword matching
        usb_device = device_link.resolve().parent
        ident_parts = []
        for attr in ("manufacturer", "product"):
            try:
                ident_parts.append((usb_device / attr).read_text().strip())
            except OSError:
                pass
        ident = " ".join(ident_parts).lower()

        if not any(kw.lower() in ident for kw in _PHONE_KEYWORDS):
            continue

        bus = _usb_bus_prefix(sysfs_path)

        phones.append({
            "card": card_num,
            "card_id": card_id,
            "bus": bus,
            "sysfs": sysfs_path,
        })

    return phones


def _find_printers() -> list[dict]:
    """Find all USB printers (/dev/usb/lp*) and their USB bus info."""
    printers = []
    usb_misc = Path("/sys/class/usbmisc")
    if not usb_misc.exists():
        return printers

    for lp_dir in sorted(usb_misc.glob("lp*")):
        dev_path = f"/dev/usb/{lp_dir.name}"
        if not os.path.exists(dev_path):
            continue

        device_link = lp_dir / "device"
        if not device_link.exists():
            continue
        sysfs_path = str(device_link.resolve())
        bus = _usb_bus_prefix(sysfs_path)

        printers.append({
            "dev": dev_path,
            "bus": bus,
            "sysfs": sysfs_path,
        })

    return printers


def _find_input_devices() -> list[dict]:
    """Find POP Phone HID input devices and their USB bus info."""
    devices = []
    for event_dir in sorted(Path("/sys/class/input").glob("event[0-9]*")):
        # Read device name from the parent inputN directory
        input_dir = event_dir.resolve().parent
        name_path = input_dir / "name"
        if not name_path.exists():
            continue
        try:
            name = name_path.read_text().strip()
        except OSError:
            continue

        if "POP Phone" not in name:
            continue

        dev_path = f"/dev/input/{event_dir.name}"
        if not os.path.exists(dev_path):
            continue

        sysfs_path = str(event_dir.resolve())
        bus = _usb_bus_prefix(sysfs_path)

        devices.append({
            "dev": dev_path,
            "bus": bus,
            "sysfs": sysfs_path,
            "name": name,
        })

    return devices


def discover_sides() -> list[Side]:
    """Discover and pair phones + printers by USB bus.

    Returns a list of Side objects (up to 2), each with a phone and printer
    on the same USB controller. Sides are labeled A and B in stable order
    (sorted by ALSA card number).

    Raises RuntimeError if hardware can't be paired.
    """
    phones = _find_pop_phones()
    printers = _find_printers()

    if not phones:
        raise RuntimeError("No POP Phones found")
    if not printers:
        raise RuntimeError("No printers found")

    sides = []
    labels = iter("AB")

    # Sort phones by card number for stable A/B assignment
    for phone in sorted(phones, key=lambda p: p["card"]):
        # Find printer on same bus
        matching = [p for p in printers if p["bus"] == phone["bus"]]
        if not matching:
            print(f"  WARNING: Phone card {phone['card']} ({phone['card_id']}) "
                  f"on bus {phone['bus']} has no matching printer")
            continue

        printer = matching[0]
        label = next(labels, "?")
        sides.append(Side(
            label=label,
            card=phone["card"],
            card_id=phone["card_id"],
            printer_dev=printer["dev"],
            usb_bus=phone["bus"],
        ))
        # Remove matched printer so it's not reused
        printers.remove(printer)

    if not sides:
        raise RuntimeError(
            f"Could not pair any phones with printers. "
            f"Phones on buses: {[p['bus'] for p in phones]}, "
            f"Printers on buses: {[p['bus'] for p in printers]}"
        )

    # Match input devices (POP Phone HID buttons) to sides by bus
    input_devs = _find_input_devices()
    for side in sides:
        matching = [d for d in input_devs if d["bus"] == side.usb_bus]
        if matching:
            side.input_dev = matching[0]["dev"]

    return sides


def setup_pop_phone_mixer(card: int):
    """Configure mixer levels for a POP Phone."""
    try:
        mixers = alsaaudio.mixers(cardindex=card)
    except Exception:
        return

    if "PCM" in mixers:
        m = alsaaudio.Mixer("PCM", cardindex=card)
        m.setvolume(80)
        print(f"  card {card}: PCM playback -> 80%")
    if "Mic" in mixers:
        m = alsaaudio.Mixer("Mic", cardindex=card)
        m.setvolume(80)
        print(f"  card {card}: Mic capture -> 80%")
    if "Auto Gain Control" in mixers:
        m = alsaaudio.Mixer("Auto Gain Control", cardindex=card)
        m.setmute(0)
        print(f"  card {card}: AGC off")


def print_topology():
    """Print discovered hardware topology (useful for debugging)."""
    phones = _find_pop_phones()
    printers = _find_printers()

    print("POP Phones:")
    for p in phones:
        print(f"  card {p['card']} ({p['card_id']}) on bus {p['bus']}")
        print(f"    sysfs: {p['sysfs']}")

    print("Printers:")
    for p in printers:
        print(f"  {p['dev']} on bus {p['bus']}")
        print(f"    sysfs: {p['sysfs']}")

    input_devs = _find_input_devices()
    print("Input Devices:")
    for d in input_devs:
        print(f"  {d['dev']} ({d['name'].strip()}) on bus {d['bus']}")
        print(f"    sysfs: {d['sysfs']}")

    print()
    try:
        sides = discover_sides()
        print(f"Paired {len(sides)} side(s):")
        for s in sides:
            input_str = s.input_dev or "none"
            print(f"  Side {s.label}: card {s.card} ({s.card_id}) + {s.printer_dev} + {input_str} [bus {s.usb_bus}]")
    except RuntimeError as e:
        print(f"Pairing failed: {e}")


if __name__ == "__main__":
    print_topology()
