"""
Card boxes: a closed sleeve, open at one short end.

Cards lie flat in a tube. The floor, the ceiling, both long walls and one
short wall are solid; the other short wall is not there at all, and that
opening is the mouth the stack comes out of. Nothing lifts off and there
is nothing to lose -- where a card well is open at one end and wants a
lid before it will stack, a box is closed all round and stacks on
whatever face you put it on.

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

A box can hold separators too. They are named, not counted: each id is
one sheet and one STL, and each says only what it wants of its own --
thickness, fit, a label, or nothing at all. Where a well's separator
carries a tab out through the open end, a box's is the bare rectangle,
the whole cavity across W and along L less the fit that lets it slide.
There is nowhere for a tab to go and nothing to hang it on: a box is
emptied by drawing the stack out of the mouth, and the sheets come with
it. Each takes its own label, which is the point of naming them -- a
sheet reading AGE II is worth more than a sheet -- and each takes its
thickness out of the stack, so the card count reports what is left.

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

# Separators: the bare rectangle of the cavity, less the fit that lets it
# slide. A well's sheet reaches a tab out through its open end to show the
# split from outside; a box has no outside to show it on, so this is the
# sheet and nothing else.
#
# Unlike a well's, the block is optional -- a section whose boxes never ask
# for a separator has no reason to state one. What it does state is what
# every sheet takes unless it says its own.
SEP_KEYS = ("thickness", "fit")
SHEET_KEYS = SEP_KEYS + ("emboss",)


def sep_block(block, at, keys):
    """A separator block, closed to the keys a sheet takes.

    Closed for the reason the notch block is: the section's numbers are
    inherited without a variant saying a word, so a typo here would go on
    to be reported against the sheet that never stated it.
    """
    if not isinstance(block, dict):
        raise ValueError(f"{at}: must be an object, got {block!r}")
    unknown = [key for key in block if key not in keys]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{at}: {named} is not something a separator takes -- it takes "
            f"{', '.join(keys)}"
        )
    return block


SEP = sep_block(BOXES.get("separator") or {}, f"{WHERE} card_boxes separator", SEP_KEYS)


def sheet_of(sheet_spec, seat):
    """The two numbers one sheet is built to: its own word over the section's.

    Neither has a default to fall back on. A sheet is only as good as the
    cavity it fills, and a guessed thickness or fit would be a sheet that
    binds or rattles rather than one that says it was never sized.
    """
    said = {**SEP, **sheet_spec}
    for key in SEP_KEYS:
        if said.get(key) is None:
            raise ValueError(
                f"{seat}: no {key} to build the sheet to -- state one here, or "
                f"once for the whole section under card_boxes.separator"
            )
    thick, fit = said["thickness"], said["fit"]
    if thick <= 0 or fit < 0:
        raise ValueError(
            f"{seat}: thickness must be positive and fit cannot be negative, "
            f"got {thick} and {fit}"
        )
    return thick, fit


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
    seps = spec.get("separators") or {}
    if not isinstance(seps, dict):
        raise ValueError(
            f"[{name}] separators must be an object keyed by separator id, got "
            f"{seps!r} -- one entry per sheet, each stating whatever it wants "
            f"of its own and taking the section's numbers for the rest"
        )

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

    sheets = []
    for sid, sheet_spec in seps.items():
        seat = f"{at} separators.{sid}"
        if sheet_spec is None:  # a bare null reads as "nothing of my own"
            sheet_spec = {}
        sheet_spec = sep_block(sheet_spec, seat, SHEET_KEYS)
        if not sid or "/" in sid or "\\" in sid:
            raise ValueError(
                f"{at} separators: {sid!r} will not do as an id -- it names an "
                f"STL, so it cannot be empty or carry a path separator"
            )

        thick, fit = sheet_of(sheet_spec, seat)
        sheet_w, sheet_l = INNER_W - fit, INNER_L - fit
        if sheet_w <= 0 or sheet_l <= 0:
            raise ValueError(
                f"{seat}: a {fit} mm fit leaves no sheet inside the "
                f"{INNER_W} x {INNER_L} mm cavity"
            )

        # Flat on the bed, which is the only way a sheet prints. The box
        # itself is stood on end further down; a rectangle has no reason to
        # follow it there.
        mesh_sep = box((0, sheet_w), (0, sheet_l), (0, thick))
        if sheet_spec.get("emboss"):
            # Onto the face, which is all a bare rectangle has to offer.
            solid, sheet_label = emboss_solid(
                sheet_spec["emboss"],
                (0, sheet_w),
                (0, sheet_l),
                thick,
                f"{seat} emboss",
                EMB,
            )
            if sheet_label["cut"]:
                mesh_sep = trimesh.boolean.difference([mesh_sep, solid])
            else:
                mesh_sep = trimesh.boolean.union([mesh_sep, solid])
            mesh_sep.merge_vertices()
            mesh_sep.update_faces(mesh_sep.nondegenerate_faces())

        sheets.append({"id": sid, "mesh": mesh_sep, "thick": thick})

    sep_stack = sum(sheet["thick"] for sheet in sheets)
    if sep_stack >= INNER_H:
        raise ValueError(
            f"[{name}] {len(sheets)} separators are {sep_stack:.1f} mm of a "
            f"{INNER_H} mm stack, leaving no room for cards"
        )
    card_stack = INNER_H - sep_stack

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

    sep_paths = []
    for sheet in sheets:
        sep_path = f"{OUTDIR}/{GAME_ID}_card_box_separator_{name}_{sheet['id']}.stl"
        sheet["mesh"].export(sep_path)
        sep_paths.append(sep_path)

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
    if sheets:
        print(
            f"    stack     {INNER_H} mm less {sep_stack:.1f} mm of separators "
            f"-> {card_stack:.1f} mm of cards"
        )
        if card_thick:
            print(
                f"    ~{card_stack / card_thick:.0f} sleeved cards + "
                f"{len(sheets)} separators"
                f"{own_note(own_checks, 'card_thickness')}"
            )
        else:
            print(
                f"    {len(sheets)} separators, and no card thickness to "
                f"estimate a card count from"
            )
    elif card_thick:
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
    for sep_path in sep_paths:
        print(f"  -> {sep_path}")
    print()
