"""Tests for hardware discovery and USB bus pairing."""

import logging
_log = logging.getLogger("cold_call.test_crash")
_log.info("test_hardware.py: importing cold_call.hardware...")
from unittest.mock import patch
from cold_call.hardware import _usb_bus_prefix, discover_sides
_log.info("test_hardware.py: imports complete")


def test_usb_bus_prefix_vl805():
    path = "/sys/devices/platform/scb/fd500000.pcie/pci0000:00/0000:00:00.0/0000:01:00.0/usb1/1-1/1-1.4/1-1.4:1.0/sound/card1"
    assert _usb_bus_prefix(path) == "0000:01:00.0"


def test_usb_bus_prefix_dwc2():
    path = "/sys/devices/platform/soc/fe980000.usb/usb3/3-1/3-1.2/3-1.2:1.0/sound/card2"
    assert _usb_bus_prefix(path) == "fe980000.usb"


def test_usb_bus_prefix_no_usb():
    path = "/sys/devices/platform/something/else"
    assert _usb_bus_prefix(path) == path


def test_discover_sides_pairs_by_bus():
    phones = [
        {"card": 1, "card_id": "Phone", "bus": "bus_a", "sysfs": "/sys/a"},
        {"card": 2, "card_id": "Phone_1", "bus": "bus_b", "sysfs": "/sys/b"},
    ]
    printers = [
        {"dev": "/dev/usb/lp0", "bus": "bus_a", "sysfs": "/sys/pa"},
        {"dev": "/dev/usb/lp1", "bus": "bus_b", "sysfs": "/sys/pb"},
    ]
    input_devs = [
        {"dev": "/dev/input/event0", "bus": "bus_a", "sysfs": "/sys/ia", "name": "POP Phone"},
        {"dev": "/dev/input/event1", "bus": "bus_b", "sysfs": "/sys/ib", "name": "POP Phone"},
    ]

    with patch("cold_call.hardware._find_pop_phones", return_value=phones), \
         patch("cold_call.hardware._find_printers", return_value=printers), \
         patch("cold_call.hardware._find_input_devices", return_value=input_devs):
        sides = discover_sides()

    assert len(sides) == 2
    assert sides[0].label == "A"
    assert sides[0].card == 1
    assert sides[0].printer_dev == "/dev/usb/lp0"
    assert sides[0].input_dev == "/dev/input/event0"
    assert sides[1].label == "B"
    assert sides[1].card == 2
    assert sides[1].printer_dev == "/dev/usb/lp1"


def test_discover_sides_no_phones():
    with patch("cold_call.hardware._find_pop_phones", return_value=[]), \
         patch("cold_call.hardware._find_printers", return_value=[{"dev": "/dev/usb/lp0", "bus": "x", "sysfs": "/sys/x"}]):
        try:
            discover_sides()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "No POP Phones" in str(e)


def test_discover_sides_no_matching_printer():
    """A phone with no printer on its bus still yields a side, minus the printer."""
    phones = [{"card": 1, "card_id": "Phone", "bus": "bus_a", "sysfs": "/sys/a"}]
    printers = [{"dev": "/dev/usb/lp0", "bus": "bus_b", "sysfs": "/sys/b"}]

    with patch("cold_call.hardware._find_pop_phones", return_value=phones), \
         patch("cold_call.hardware._find_printers", return_value=printers), \
         patch("cold_call.hardware._find_input_devices", return_value=[]):
        sides = discover_sides()

    assert len(sides) == 1
    assert sides[0].label == "A"
    assert sides[0].card == 1
    assert sides[0].printer_dev is None


def test_discover_sides_no_printers_at_all():
    """Printers unpowered/unplugged: sides still discovered for audio testing."""
    phones = [
        {"card": 1, "card_id": "Phone", "bus": "bus_a", "sysfs": "/sys/a"},
        {"card": 2, "card_id": "Phone_1", "bus": "bus_b", "sysfs": "/sys/b"},
    ]

    with patch("cold_call.hardware._find_pop_phones", return_value=phones), \
         patch("cold_call.hardware._find_printers", return_value=[]), \
         patch("cold_call.hardware._find_input_devices", return_value=[]):
        sides = discover_sides()

    assert len(sides) == 2
    assert [s.label for s in sides] == ["A", "B"]
    assert all(s.printer_dev is None for s in sides)


def test_discover_sides_one_printer_only():
    """One printer powered: that side prints, the other degrades."""
    phones = [
        {"card": 1, "card_id": "Phone", "bus": "bus_a", "sysfs": "/sys/a"},
        {"card": 2, "card_id": "Phone_1", "bus": "bus_b", "sysfs": "/sys/b"},
    ]
    printers = [{"dev": "/dev/usb/lp0", "bus": "bus_b", "sysfs": "/sys/pb"}]

    with patch("cold_call.hardware._find_pop_phones", return_value=phones), \
         patch("cold_call.hardware._find_printers", return_value=printers), \
         patch("cold_call.hardware._find_input_devices", return_value=[]):
        sides = discover_sides()

    assert sides[0].printer_dev is None
    assert sides[1].printer_dev == "/dev/usb/lp0"


def test_discover_sides_sorted_by_card():
    """Sides should be labeled A/B in card-number order."""
    phones = [
        {"card": 5, "card_id": "Phone_1", "bus": "bus_b", "sysfs": "/sys/b"},
        {"card": 2, "card_id": "Phone", "bus": "bus_a", "sysfs": "/sys/a"},
    ]
    printers = [
        {"dev": "/dev/usb/lp0", "bus": "bus_a", "sysfs": "/sys/pa"},
        {"dev": "/dev/usb/lp1", "bus": "bus_b", "sysfs": "/sys/pb"},
    ]

    with patch("cold_call.hardware._find_pop_phones", return_value=phones), \
         patch("cold_call.hardware._find_printers", return_value=printers), \
         patch("cold_call.hardware._find_input_devices", return_value=[]):
        sides = discover_sides()

    assert sides[0].card == 2
    assert sides[0].label == "A"
    assert sides[1].card == 5
    assert sides[1].label == "B"
