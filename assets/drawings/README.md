# Department Response Worksheets

Source artwork for the worksheet printed at the bottom of each prompt
dispatch. Participants record the other party's response here with stamps,
stickers, and tape.

Bake these into print-ready 1-bit images with:

    uv run python scripts/prep_drawings.py

That writes `assets/images/{theme}_drawing.png` at the 576px print width,
which `printer.py` appends to the dispatch. A department with no file here
simply prints without a worksheet — that's why the apathy test department
has none.

## Filenames

One file per deployed department, named for its theme key in
`assets/departments.yaml`.

## Note on `ambient_belonging.png`

This arrived from the designers as
`2020_08_DesignFest_Graphics_Conditional Invitation-06.png` — the second of
two files carrying the Conditional Invitation name. The `-02`/`-06` suffixes
are Illustrator artboard numbers, and `-06` was exported under the
neighboring artboard's name.

It belongs to Ambient Belonging: the archive holds exactly six worksheets for
the six deployed departments, and the START/END path fits "Maintaining the
Conditions for Togetherness" where the RSVP invite form in `-02` is plainly
Conditional Invitations. Confirmed with the designer.

Don't rename it back to match the original export.
