# Cold Calls — Receipt Design Standard

This document governs the printed dispatch. Where a decision is specified
here, it is settled; implement it and move on. Where it is not, it belongs in
Open Questions at the bottom until resolved.

## The medium

| | |
|---|---|
| Paper | 80mm thermal roll |
| Printable width | 72.1mm — 576px at 203dpi |
| Colour depth | 1-bit. No grey, no antialiasing |
| Dot size | 0.125mm |
| Length | Unbounded, but paper is a cost |

Three consequences govern everything below.

**Nothing thinner than 2px.** A single dot is 0.125mm and the thermal head
spreads. Thinner strokes drop out or smear shut.

**No tone.** Every tonal asset is thresholded to 1-bit before printing, never
dithered. Dithered line art speckles.

**No optical adjustment.** There is no subpixel positioning. Every element
lands on a whole dot.

## One voice

The receipt is set in a single face throughout. It is issued by a machine, on
behalf of an institution, and it reads as one artefact rather than as a
letterhead with a body pasted underneath.

**IBM Plex Mono**, Regular and Bold, vendored at
`assets/fonts/IBMPlexMono-{Regular,Bold}.ttf`. SIL OFL 1.1, © 2017 IBM Corp;
the licence travels with it. Vendored rather than taken from the system so a
station renders identically wherever it is built.

The face is chosen for the fiction and for the room. IBM commissioned Plex as
the successor to its own typewriter lineage, which puts the dispatch in the
register of machine-issued government paperwork rather than of design. The
monospace rhythm is doing that work; a grotesque reads as more legible but as
less issued.

Monospace costs width — roughly one extra line per long question against a
proportional face. That cost is accepted.

Emphasis is Bold. There is no third weight and no synthesised one; thinning
strokes by supersampling and thresholding is unpredictable under dot spread.

Graphics supplied by the designers are never redrawn. The seals and worksheets
are used as authored, and they carry their own serif lettering — that second
face belongs to the authors and stays.

## Structure

The dispatch has four zones, in this order.

| Zone | Contains |
|---|---|
| Head | Seal, banner, form number, priority |
| Procedure | The notice, then the numbered steps |
| Question | The question, alone |
| Field | The field label, then the worksheet |
| Foot | Agency name, tagline, sign-off |

**The procedure is consolidated, not interleaved.** The steps are listed
together and read once, rather than threaded between the question and the
field. The reader is holding a handset in a loud room and needs the question
to be the most findable thing on the page, not the object of step one — and
they glance back mid-conversation, which rewards instructions living in one
known place over a list to re-scan.

The cost is accepted: interleaved steps teach a first-timer better, and a
consolidated block is easier to skip. The audio narration does that teaching.

**The agency signs off at the foot; it does not title the head.** The seal
already names the agency at the top, so setting the name in type there as well
says it twice. At the foot it closes the document, the way a form is signed.

**The field label names what to produce; the artwork says where it goes.** A
label that repeats a word the artwork already prints is wasted — the label for
the one-word worksheet is REASON, not ONE WORD.

## Type

**Every size has a role.** The scale is functional, not minimal.

| Size | Role |
|---|---|
| 40 | The question |
| 28 | The banner — APPROVED DIALOGUE |
| 20 | Form number and priority; the procedure; the field label; the agency name; everything on the status receipt |
| 16 | The tagline and the sign-off — the signature block at the foot |

A real government form is an accreted object: a banner size, a body size, a
fine-print size, and whatever was added the year a field was inserted. That
mild untidiness is what makes it read as issued rather than art-directed, and
it is deliberate here.

The designers' worksheets carry two sizes in a 2:1 ratio, and that was
initially taken as the rule. It is not: those are designed objects made by
designers, and the receipt is meant to look like an artefact. The worksheets
govern rule weight, margin and ink coverage, not the type scale.

A new size is added when an element has a role no existing size serves, and it
is recorded above. Sizes that drift without a role are sloppiness, not period
character.

**Caps everywhere except the question and the instructions.** Those two are
read, so they are set as sentences. Everything else is the form talking about
itself — banner, form number, priority, department, tagline, field labels —
and it is set in caps and tracked out.

Caps cost width, and in a monospace face that cost is fixed. Where a caps line
will not fit the column, it is broken into the fields it actually contains
rather than set smaller: form number and priority are two lines, not one piped
line, because in caps the combined line overran the column for three of the
seven departments.

The sign-off is prose and stays in sentence case. It is the form thanking the
reader rather than labelling itself, which puts it with the question and the
instructions.

**Tracking is what makes caps read as stamped.** The designers track their
capitals generously on both the seals and the worksheet labels. Untracked caps
read as merely typed.

**Measure before size.** A question that stacks into a tower is a wrap problem
before it is a size problem. Fill the column before reducing type.

**Size and measure are one decision.** The face is monospace, so the column
holds a whole number of characters and the fractional remainder is wasted. At
40px Plex Mono advances 24px, so a 526px column holds 21.9 characters — and a
22-character phrase misses by 2px and rags badly. Choosing a size means
choosing how many characters fit.

**Rags are balanced, not greedy.** Greedy fill packs early lines and leaves a
stub, which on centred display type reads as an accident. Lines are
redistributed over the same line count to even the rag.

## Space

**Margin is 25px each side** — 4.3% of width. An element may claim more if it
needs the room; none may claim less.

**Zone dividers are a double rule** — 3px over 2px, separated by 6px, spanning
the column. Doubled to tell them apart from the rules inside the designers'
worksheets, which are lines to write on: at a single weight the two read as
the same kind of object, and nothing distinguished "this divides a section"
from "write here". Thick over thin is the ledger and form convention.

**A single 3px rule is a mark, not a divider** — 0.53% of width, measured off
the worksheets. Used for the short rule that closes the sign-off.

2px is the floor the medium allows, and the thin rule sits on it. It survives
because it is a long continuous horizontal, the most forgiving shape for a
thin stroke under dot spread. Nothing else on the receipt may be that thin.

**Space separates before a rule does.** A rule is for a genuine division, not
for spacing.

**White is the ground.** These are forms to be written on. Ink coverage on the
worksheets runs between 0.6% and 3.1%; the receipt should not be denser
without reason.

## Images

**Seals and worksheets are baked to 1-bit ahead of print**, never converted at
print time. Baking scripts own the threshold, and the threshold is chosen so
the finest stroke in the asset survives the downscale.

**The small seal is the printed one.** 288px. The 576px variant is a fallback.

**Artwork is trimmed to its own edges** before scaling, so framing is set by
the layout and not by the exporter. Seals only — the worksheets keep the
whitespace they were drawn with.

**The space above a worksheet is the author's, not residue.** Several
worksheets carry a large blank band at the top. It is deliberate, it is left
alone, and nothing in the layout should close it up. It is the largest gap on
the receipt by design.

## Provenance

The measurements above are taken from the six worksheets supplied by the
designers in `assets/drawings/`, normalised as a percentage of sheet width.
That artwork is the reference for this standard. Where this document and the
printed result disagree, the printed result wins and this document is
rewritten.

## Open questions

1. Whether 40px is the right question size. It is what the column and the
   measure currently settle on, not a figure anyone chose.
2. What governs receipt length. Nothing currently limits how long a dispatch
   may run beyond the raster ceiling.
