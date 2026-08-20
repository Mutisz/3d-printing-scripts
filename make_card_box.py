"""
Card boxes: a closed sleeve, open at one short end.

Cards lie flat in a tube. The floor, the ceiling, both long walls and one
short wall are solid; the other short wall is not there at all, and that
opening is the mouth the stack comes out of. Nothing lifts off and there
is nothing to lose -- where a well-style card holder is open down both
long sides and wants a lid before it will stack, a box is closed all
round and stacks on whatever face you put it on.

What it gives up is the reach-in: there is no picking a card out of the
middle. So the ceiling and the floor each carry a slot, running back from
the mouth with a rounded end and wide enough to put a thumb through. Two
of them rather than one because a single slot only lets you press down on
the top card, while a pair lets you pinch the stack -- thumb above and
finger below -- which is what gets the last few cards out of a box that
has no other way in.

A box is stated lying down, the way it sits in an insert -- W across, L
from the closed end to the mouth, and H the stack. It is exported
standing on that closed end with the mouth pointing up, which is the only
orientation worth printing it in: every wall is vertical, the whole part
is one constant cross-section over a solid cap, and there is not an
overhang in it anywhere. So the STL measures W x H x L rather than
W x L x H, which is why the report marks its sizes `lying down` rather
than leaving the difference to be found out in the slicer.

That orientation is also why both slots run out to the mouth rather than
sitting as holes in the middle of their faces. Standing up, the mouth is
the top of the print, so a slot is nothing more than where its face
stops, and the rounded end only ever takes material away on the way up.

A box can be labelled: emboss puts text on the ceiling, the face that
shows while the box lies in its insert, and only there -- the floor is
slotted the same but carries nothing. The slots are cut before the words
are placed and the words are given the ceiling that is left, so a label
never runs into one.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_card_box.py <game_id>
"""

import math

import trimesh

from gameconfig import (
    box,
    checks_of,
    dims,
    load_game,
    need,
    outdir,
    own_note,
    parse_game_id,
    validation,
)
from label import EMB_MARGIN, emboss_defaults, emboss_solid

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

# Emptied before anything is read, so dropping the section from the file
# clears the boxes it used to build rather than stranding them.
OUTDIR = outdir(GAME_ID, "card_boxes")

BOXES = CFG.get("card_boxes")
if not BOXES:  # an ordinary state, not an error: exit clean so runners can tell
    print(f"{WHERE}: no 'card_boxes' section, nothing to build")
    raise SystemExit(0)

T = need(BOXES, "wall", WHERE)  # the two long walls and the closed end
F = need(BOXES, "floor", WHERE)
C = BOXES.get("ceiling")
if C is None:  # the two faces are the same problem, so one number does for both
    C = F
VARIANTS = need(BOXES, "variants", WHERE)
EMB = emboss_defaults(BOXES, f"{WHERE} card_boxes")
VALID = validation(BOXES, f"{WHERE} card_boxes")

if T <= 0 or F <= 0 or C <= 0:
    raise SystemExit(f"{WHERE} card_boxes: wall, floor and ceiling must be positive")

# The thumb slots, one shape for both faces. A thumb is a thumb whatever
# size the card is, so unlike a corner post these are millimetres and not a
# fraction of anything -- the same slot on a small box and a large one.
NOTCH_KEYS = ("width", "reach")
NOTCH_WIDTH = 25.0  # across W, centred
NOTCH_REACH = 25.0  # back from the mouth


def notch_block(block, at):
    """A notch block, closed to the two numbers a slot takes."""
    if not isinstance(block, dict):
        raise ValueError(f"{at} notch: must be an object, got {block!r}")
    unknown = [key for key in block if key not in NOTCH_KEYS]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{at} notch: {named} is not something a slot takes -- it takes "
            f"{', '.join(NOTCH_KEYS)}"
        )
    return block


NOTCH = notch_block(BOXES.get("notch") or {}, f"{WHERE} card_boxes")


def notch_of(spec, at):
    """The slot a variant gets: the section's numbers under its own."""
    own = notch_block(spec.get("notch") or {}, at)
    said = {**NOTCH, **own}
    width = said.get("width", NOTCH_WIDTH)
    reach = said.get("reach", NOTCH_REACH)
    if width <= 0 or reach <= 0:
        raise ValueError(
            f"{at} notch: width and reach must be positive, got {width} and {reach}"
        )
    return width, reach


def notch_cut(W, L, H, width, reach):
    """The thumb slots, as the solids to take out of a blank.

    One through the ceiling and the same one through the floor, so the stack
    is pinched rather than only pressed: a thumb on the top card and a
    finger under the bottom one, which is what gets the last few cards out
    of a box that has no other way in.

    Straight sides from the mouth and a rounded end, the shape the tray
    notches already use. Both run right out past the mouth, which is what
    keeps them printable -- standing up that is the top of the print, so
    each slot is only ever where its face stops.
    """
    over = 2.0
    cx = W / 2
    r = min(width / 2, reach)  # semicircular once the slot is deep enough
    flat = width / 2 - r  # half-length of the straight-sided part, may be 0
    inner = L - reach  # where the slots stop short of the closed end

    parts = []
    for zr in ((-over, F + over), (H - C - over, H + over)):  # floor, then ceiling
        parts.append(box((cx - width / 2, cx + width / 2), (inner + r, L + over), zr))
        if flat > 1e-9:
            parts.append(box((cx - flat, cx + flat), (inner, inner + r), zr))
        for offset in {-flat, flat}:  # a set, so a semicircle adds one cylinder
            cyl = trimesh.creation.cylinder(radius=r, height=zr[1] - zr[0], sections=64)
            cyl.apply_translation([cx + offset, inner + r, (zr[0] + zr[1]) / 2])
            parts.append(cyl)
    return parts


print("=" * 60)
print(f"Card Box Generator -- {CFG['game']['name']}")
print("=" * 60)
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} card_boxes.variants.{name}"
    W, L, H = dims(need(spec, "size", at), 3, at, "size")

    INNER_W = W - 2 * T  # between the long walls
    INNER_L = L - T  # closed end to the mouth
    INNER_H = H - F - C  # floor to ceiling, which is the stack

    if INNER_W <= 0 or INNER_L <= 0 or INNER_H <= 0:
        raise ValueError(
            f"[{name}] outside {W} x {L} x {H} mm leaves nothing inside "
            f"{T} mm walls, a {F} mm floor and a {C} mm ceiling"
        )

    sleeve, clear, card_thick, own_checks = checks_of(spec, at, VALID)
    if sleeve and (
        INNER_W + 1e-9 < sleeve[0] + clear or INNER_L + 1e-9 < sleeve[1] + clear
    ):
        raise ValueError(
            f"[{name}] the {INNER_W} x {INNER_L} mm cavity is too small for a "
            f"{sleeve[0]} x {sleeve[1]} mm sleeve with {clear} mm clearance, "
            f"which needs {sleeve[0] + clear} x {sleeve[1] + clear} mm -- grow "
            f"the outside size or thin the walls"
        )

    width, reach = notch_of(spec, at)
    if width > INNER_W + 1e-9:
        raise ValueError(
            f"[{name}] a {width} mm slot is wider than the {INNER_W} mm cavity "
            f"it is cut over, so it would run out through the long walls -- and "
            f"those are what a box is stiff for. State at most {INNER_W}"
        )
    if reach >= INNER_L:
        raise ValueError(
            f"[{name}] a {reach} mm slot reaches the whole {INNER_L} mm from the "
            f"mouth to the closed end, leaving no ceiling to hold the walls "
            f"apart -- state less than {INNER_L}"
        )

    over = 2.0  # overshoot so cuts clear the outer faces

    mesh = trimesh.boolean.difference(
        [
            box((0, W), (0, L), (0, H)),  # solid blank
            # One cut hollows it and takes the mouth wall out with it, by
            # running past that face rather than stopping at it.
            box((T, W - T), (T, L + over), (F, H - C)),
            *notch_cut(W, L, H, width, reach),
        ]
    )

    label = spec.get("emboss")
    if label and L - reach < 2 * EMB_MARGIN:
        # Caught here rather than left to the label, which would only be able
        # to report the room it was given as a negative number.
        raise ValueError(
            f"[{name}] a {reach} mm slot leaves {L - reach:.1f} mm of ceiling "
            f"for the label, inside the {EMB_MARGIN} mm margin a label keeps "
            f"clear at each end -- shorten the reach or drop the emboss"
        )
    if label:
        # On the ceiling, in what the slot left of it. Built as though the
        # ceiling were a plate lying on the bed and then lifted into place,
        # because what a cut label has to be checked against is the ceiling
        # it is sunk into, not how high off the ground that ceiling is.
        solid, label_info = emboss_solid(
            label, (0, W), (0, L - reach), C, f"{at} emboss", EMB
        )
        solid.apply_translation([0, 0, H - C])
        if label_info["cut"]:
            mesh = trimesh.boolean.difference([mesh, solid])
        else:
            mesh = trimesh.boolean.union([mesh, solid])

    # Stand it on its closed end, mouth up, which is the way it prints and so
    # the way it is written out. Everything above was reasoned about lying
    # down, which is the way it is used and the way its size reads.
    stand = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])
    mesh.apply_transform(stand)
    mesh.apply_translation([0, H, 0])  # back into the positive octant

    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_card_box_{name}.stl"
    mesh.export(path)

    print("-" * 60)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm, lying down")
    print(f"    inside    {INNER_W} x {INNER_L} mm, {INNER_H} mm of stack")
    if sleeve:
        print(
            f"    sleeve    {sleeve[0]} x {sleeve[1]} mm + {clear} mm clearance -> "
            f"{INNER_W - sleeve[0] - clear:.1f} / {INNER_L - sleeve[1] - clear:.1f} "
            f"mm to spare{own_note(own_checks, 'sleeve', 'clearance')}"
        )
    print("  Capacity")
    if card_thick:
        print(
            f"    stack     {INNER_H} mm -> ~{INNER_H / card_thick:.0f} sleeved "
            f"cards{own_note(own_checks, 'card_thickness')}"
        )
    else:
        print(
            f"    stack     {INNER_H} mm, and no card thickness to estimate a "
            f"card count from"
        )
    print(f"  -> {path}")
    print()
