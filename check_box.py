"""
Box layout: where every part goes in the game box, and whether it all fits.

Not a generator -- this builds nothing and exports nothing but a picture.
It reads the `box` section of games/<game_id>.json, works out from it where
every part actually sits, and says whether the arrangement holds together:
that it is all inside the box, that nothing is in the same place as
anything else, and that everything off the floor has something under it.

The arrangement is stated the way you would describe it out loud, as one
list. Its entries follow each other across the box, left to right. Any
entry can be a run of its own instead of a single thing -- "along" says
which way that run goes, "place" says what is in it -- and its contents
follow each other along that axis, from the corner the run was handed.
Runs hold runs, so a pile of boards inside one slot, or a row of trays end
to end inside another, is written where it actually is.

Nothing states a position: an entry starts where the entry before it in
the same run ends. So a resized tray moves what is stacked on it, leaves
the rest of the box alone, and the check comes out of date the moment the
numbers do rather than a week later on the kitchen table.

Objects are named by id, and an id is anything this file defines: a card
holder, a card box, a tray, or an entry under box.extras for the things no
script here prints -- boards, rulebooks, bags. Each is named once.

What it cannot do is arrange the box for you. It checks the arrangement you
wrote, and reports what is left over.

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
