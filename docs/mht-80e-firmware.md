# MHT-80E Firmware Notes

Everything here came from static analysis of `MHT-P80E_20260317(1).bin`, the
upgrade image supplied by the vendor. Nothing in this document requires
sending anything to a printer, and nothing here should be turned into
experimental commands — we have already lost one printer.

## Why this matters

The printers brick. A bricked MHT-80E reboots into its bootloader (IAP mode),
stops being a printer, and enumerates as a USB mass-storage device. Recovery
is easy once you know the trick (see below), but the cause was a mystery for a
while: some graphics bricked printers and others did not.

The cause is now known and fixed — see "The bug" below.

## Recovering a bricked printer

A printer in IAP mode appears as a FAT12 USB drive labelled `MHT_IAP`,
typically `/dev/sdc`. The drive contains a `Readme.txt` (GBK-encoded Chinese)
with the vendor's instructions:

1. Connect the printer to a computer over USB.
2. Copy the upgrade file onto the drive named `MHT_IAP`.
3. Power-cycle the printer.

Keep a copy of the `.bin` somewhere findable. Without it a bricked printer
stays bricked.

## The firmware image

The image is **not encrypted**. It is XOR-obfuscated with the single byte
`0xa3`:

```python
data = open("MHT-P80E_20260317(1).bin", "rb").read()
firmware = bytes(b ^ 0xA3 for b in data)
```

Evidence, in case the key changes in a future release:

- Raw entropy is 6.875 bits/byte with `0xa3` at 12.4% of all bytes. Encrypted
  or compressed data is ~8.0 and flat; a 12% spike rules both out.
- There is a 310-byte run of `0xa3` at offset `0x238da` — zero padding.
- After XOR, the image begins with the ASCII string
  `DZ_Printer_FeieM58DZ&%#` (Feie is a Chinese thermal printer vendor).
- The descrambled image contains 498 occurrences of `0x4770` (`bx lr`),
  the standard ARM Thumb function return.

So: **ARM Thumb, little-endian, XOR 0xa3.** Disassemble with capstone
(`CS_ARCH_ARM`, `CS_MODE_THUMB`). Note that Thumb decode density is a useless
signal on its own — random bytes decode at ~96% — so verify with strings,
`bx lr` counts, or known structure instead.

## The command dispatcher

At offset `0x9810` in the descrambled image, the ESC/POS command parser
dispatches on the incoming byte:

```
0x9810  cmp   r2, #0x1b        ESC  -> handler
0x9814  bgt   0x982a           higher values handled below
0x9816  sub.w r2, r2, #0x14    rebase to 0x14
0x981a  cmp   r2, #7
0x981c  bhs   0x9904           reject if out of range
0x981e  tbb   [pc, r2]         jump table for 0x14-0x1a
0x982a  cmp   r2, #0x1f        US   -> handler
0x9830  cmp   r2, #0x1c        FS   -> handler
0x9834  cmp   r2, #0x1d        GS   -> handler
0x9838  cmp   r2, #0x1e        RS   -> handler
0x983e  cmp   r2, #0x20
0x9842  cmp   r2, #0xff
```

A second stage sits above this one. At `0x97ee` the parser compares against
`0x13`, branches to a handler for that value, sends anything greater to
`0x9810` (the code above), and otherwise indexes a `tbb` table at `0x97f8`
covering `0x00`-`0x12`. So the parser indexes the **whole `0x00`-`0x20` range**
plus `0xff`.

Being indexed is not the same as being actioned. `0x0b`-`0x0f` branch to a
shared stub at `0x9904`, and several other table entries land in runs of
`0xbf00` NOPs that fall through to common code — functionally the same as the
stub. Distinguishing a real handler from a fallthrough needs each convergence
point followed, which has not been done. Note also that `0x00` is in the table
and every receipt is mostly `NUL`, so dispatch alone is clearly not harmful.

The bytes handled by the `0x9810` stage are:

| Byte | Name | Dispatched via |
|---|---|---|
| `0x14`-`0x1a` | DC4, NAK, SYN, ETB, CAN, EM, SUB | `tbb` jump table |
| `0x1b` | ESC | explicit compare |
| `0x1c` | FS | explicit compare |
| `0x1d` | GS | explicit compare |
| `0x1e` | RS | explicit compare |
| `0x1f` | US | explicit compare |

`DLE (0x10)` is not in this dispatcher — it is handled on the separate
real-time command path, which has **not** been examined.

## The bug

`_sanitize_raster` in `src/cold_call/printer.py` exists because the firmware
scans raster pixel data for these command bytes. It replaced each dangerous
byte with a one-bit neighbour, which sounds safe and was not:

| Old mapping | Target | Status |
|---|---|---|
| `ESC 0x1b` -> `0x1a` | SUB | **dispatched** via the tbb table |
| `FS 0x1c` -> `0x1e` | RS | **dispatched** at `0x9838` |
| `GS 0x1d` -> `0x1f` | US | **dispatched** at `0x982a` |
| `DLE 0x10` -> `0x11` | DC1 | not in this dispatcher |

Three of the four escapes turned a command byte into a *different* command
byte. The sanitizer was manufacturing the bytes it existed to remove, in
direct proportion to how much `ESC`/`FS`/`GS` an image contained — which is
why one particular graphic bricked printers and most did not.

Measured over the full prompt corpus (175 dispatches), the old sanitizer left
**132,977** command bytes in the raster stream, and **every single dispatch**
carried at least one. `US` (65,759) and `RS` (36,027) dominated, and both were
manufactured rather than naturally occurring.

## The fix

Sanitize `0x10` and `0x14`-`0x1f`, flipping bit 5 (`^ 0x20`) so every one of
them lands in `0x30`-`0x3f`. The parser rejects everything above `0x20`, so
the targets are inert, and it is still a single bit flip — one pixel.

Cost across the corpus: 0.68% of raster bytes altered, ~904 pixels per
receipt out of 1.07 million, or 0.085% of pixels. Not perceptible.

`tests/test_raster_safety.py` renders all 175 prompts across all 7 departments
and asserts that no byte in the dispatched range survives. It keeps its own
copy of the byte list so the test is the specification rather than an echo of
the implementation.

## How a printer actually bricks

Entering IAP mode is a deliberate code path, not memory corruption:

| Address | What it does |
|---|---|
| `0x13950` | `NVIC_SystemReset` — reads AIRCR, masks PRIGROUP, ORs `0x05fa0000`, adds `4` (`SYSRESETREQ`), stores to `0xe000ed0c`, then spins at `b .` |
| `0x139aa` | IAP entry — checks/stores magic `0x12345678`, then calls `0x13950` |
| `0x13a44` | Reads three bytes from the receive stream and calls `0x139aa` if they are `0x18 0x19 0x01` |
| `0xeb60` | Blocking get-next-byte from the receive ring buffer (spins on a count, reads `buf[idx]`, increments) |

So the documented brick sequence is **`18 19 01`** — CAN, EM, `0x01` — arriving
consecutively in the byte stream.

**Caveat: `0x13a44` has not been shown to be reachable.** A linear sweep of the
whole image finds no `bl` and no `b` targeting it, and no 32-bit pointer to it
or to `0x13a45`. It is either invoked register-indirect from a dispatch table
that has not been resolved, or it is dead code. What the function *would* do if
called is unambiguous; that it is wired up is not established.

A second IAP path exists at `0x13858`: a state byte compared against `3`, and
if equal, `0x139aa` is called. What sets that byte is not known. There is also
a button-polling path at `0x13b48` that reaches `NVIC_SystemReset` after ~0x12
poll iterations, which is presumably the intended hardware recovery combo.

### Why this matters for the sanitizer

The old table did not touch `0x18` or `0x19`. Across the 175-prompt corpus it
left **25,291** `CAN` bytes and — more to the point — **250 occurrences of the
two-byte prefix `18 19`**. Every one of those was a brick if the following
pixel byte happened to be `0x01`. It never was, in this corpus. That is luck,
not margin, and it matches the observed behaviour: one graphic bricked
printers and the rest did not.

The current table maps `0x18`->`0x38` and `0x19`->`0x39`, so there are zero
`CAN` bytes in the output and the sequence is unreachable regardless of whether
`0x13a44` is live.

## Still unverified

- The `DLE (0x10)` real-time command path. Its escape target `0x30` is inert
  according to the parser above, but that parser is not the one that handles
  DLE.
- `0x20` and `0xff` also appear as dispatch cases at `0x983e`-`0x9842`.
  `0xff` is solid black and cannot be remapped, so this dispatcher cannot
  normally be reading raster payload — the leak from pixel data into the
  command parser is conditional, and the condition is not understood.
- Whether the XOR key is stable across firmware releases.
