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

## Type

**Every size has a role.** The scale is functional, not minimal.

| Size | Role |
|---|---|
| 40 | The question |
| 28 | The banner — APPROVED DIALOGUE |
| 20 | Department name; instructions |
| 18 | Form number and priority |
| 16 | Tagline |

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

**Caps are for labels, not for reading.** Short labels are set in caps and
tracked out — FIVE, RSVP, EXPECTATION, and the header lines. Sentences are set
in sentence case.

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

**Rule weight is 3px** — 0.53% of width. One weight throughout.

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
the layout and not by the exporter.

## Provenance

The measurements above are taken from the six worksheets supplied by the
designers in `assets/drawings/`, normalised as a percentage of sheet width.
That artwork is the reference for this standard. Where this document and the
printed result disagree, the printed result wins and this document is
rewritten.

## Open questions

1. Whether the question is set in caps or sentence case. Caps match the form
   tradition; the questions run to 95 characters, which is long for caps.
2. Whether 40px is the right question size. It is what the column and the
   measure currently settle on, not a figure anyone chose.
3. Whether the worksheets' baked-in top whitespace is design or export
   residue, and whether to trim it.
4. What governs receipt length. Nothing currently limits how long a dispatch
   may run beyond the raster ceiling.
