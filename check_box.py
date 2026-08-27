"""
Box layout: where every part goes in the game box, and whether it all fits.

Not a generator -- this builds nothing and exports nothing but a picture.
It reads the `box` section of games/<game_id>.json, works out from it where
every part actually sits, and says whether the arrangement holds together:
that it is all inside the box, that nothing is in the same place as
anything else, and that everything off the floor has something under it.

The arrangement is stated the way you would describe it out loud. Layers
stack up the box, bottom first. Each layer divides along the box into
sections. Each section lines its objects up across the box, left to right.
Nothing states a position: a layer starts where the layers below it end, a
section where the sections before it end, an object where the object before
it ends. So a resized tray moves everything after it and the check comes
out of date the moment the numbers do, rather than a week later on the
kitchen table.

Objects are named by id, and an id is anything this file defines: a card
holder, a card box, a tray, or an entry under box.extras for the things no
script here prints -- boards, rulebooks, bags. An object longer than its
section, or taller than its layer, reaches into the next one; repeat its id
there to reserve the band it takes up.

What it cannot do is arrange the box for you. It checks the arrangement you
wrote, reports what each section has left over, and draws a rough plan of
each layer so the leftovers are somewhere you can see them.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 check_box.py <game_id>
"""

import boxlayout
from gameconfig import load_game, outdir, parse_game_id

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

# Emptied before anything is read, as the generators empty theirs, so a
# preview left behind by an arrangement since deleted cannot be mistaken
# for this one.
OUTDIR = outdir(GAME_ID, "box")

if not CFG.get("box"):  # an ordinary state: a game can be printed unpacked
    print(f"{WHERE}: no 'box' section, nothing to check")
    raise SystemExit(0)

REPORT = boxlayout.check(CFG, WHERE)
boxlayout.show(REPORT)

# Exported even when the layout is wrong, since a picture of what went
# wrong is worth more than a picture of what did not.
PATH = boxlayout.preview(REPORT, f"{OUTDIR}/{GAME_ID}_box_preview.stl")
print(f"  -> {PATH}")
print()

if REPORT.errors:
    count = len(REPORT.errors)
    raise SystemExit(
        f"{WHERE}: the layout does not hold -- {count} "
        f"{'problem is' if count == 1 else 'problems are'} listed above"
    )
