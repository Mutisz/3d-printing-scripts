"""
Card holders: top-loaded tray, open top, open long sides.

Cards lie flat and stack upward, dropped in through the open top. The floor
and the two short end walls are solid and full height. The two long walls
are gone but for a short fragment at each corner -- four posts that leave
the long sides open to reach in from.

Those openings are shorter than a card's 91 mm length, so the corner posts
block a card from sliding straight out sideways; it would have to rotate
first. Access without escape.

Either packing axis is fine; pack_axis names the dimension that repeats
down the row. "L" butts the solid end walls together, so every holder keeps
both long sides exposed and cards stay reachable while boxed. "W" butts the
open long sides together for a shorter row -- access is blocked in the box,
which costs nothing when the holders come out to play.

A variant is stated by its outside dimensions, as a tray is: what has to
fit the game box is the hard constraint, and the cavity is what is left
inside the walls. The sleeve size sets nothing. State one -- once for the
section, or per variant for a holder taking a different card -- and it is
checked against the cavity that came out; leave it out and nothing is
checked.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_card_holder.py <game_id>
"""

import trimesh

from gameconfig import box, load_game, need, outdir, parse_game_id, report_mesh

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

# Emptied before anything is read, so dropping the section from the file
# clears the holders it used to build rather than stranding them.
OUTDIR = outdir(GAME_ID, "card_holders")

HOLDERS = CFG.get("card_holders")
if not HOLDERS:  # an ordinary state, not an error: exit clean so runners can tell
    print(f"{WHERE}: no 'card_holders' section, nothing to build")
    raise SystemExit(0)

T = need(HOLDERS, "wall", WHERE)
F = need(HOLDERS, "floor", WHERE)
CARD_THICK = need(HOLDERS, "card_thickness", WHERE)
VARIANTS = need(HOLDERS, "variants", WHERE)

# Both only ever check a cavity, never size one. The sleeve is the section's
# default, used by every variant that does not state its own; clearance is
# how much bigger than the sleeve the cavity has to come out.
SLEEVE = HOLDERS.get("sleeve")
CLEAR = HOLDERS.get("clearance", 0.0)

# Separators: a flat sheet the full size of the cavity, so it stands proud
# of the cards and is easy to catch. A tab each side reaches out through the
# open long side, showing the split from outside the holder. The tab is as
# long as that opening allows, so it is not configured: it follows the
# variant's corner posts, less the same fit as the sheet.
SEP = need(HOLDERS, "separator", WHERE)
SEP_T = need(SEP, "thickness", f"{WHERE} separator")
SEP_FIT = need(SEP, "fit", f"{WHERE} separator")
SEP_TAB_OUT = SEP.get("tab_out")
if SEP_TAB_OUT is None:  # null means "land flush with the outer wall"
    SEP_TAB_OUT = T

SEP_CACHE = {}  # variants sharing a cavity share one sheet, so build it once


def dims(value, count, at, what):
    """A list of `count` positive numbers, or a message naming the key."""
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        out = None
    if out is None or len(out) != count:
        raise SystemExit(f"{at}: {what} must be {count} numbers in mm, got {value!r}")
    if any(v <= 0 for v in out):
        raise SystemExit(f"{at}: {what} must be positive, got {value!r}")
    return out


def sleeve_of(spec, at):
    """The sleeve to check against: the variant's, else the section's.

    None when neither states one, which is not an error -- it only means
    there is nothing to check the cavity against.
    """
    size = spec.get("sleeve", SLEEVE)
    return None if size is None else dims(size, 2, at, "sleeve")


def separator(sheet_w, sheet_l, tab_len):
    """Flat sheet with a tab each side, laid out print-ready on the bed."""
    key = (sheet_w, sheet_l, tab_len)
    if key not in SEP_CACHE:
        tab_y0 = (sheet_l - tab_len) / 2
        tab_y = (tab_y0, tab_y0 + tab_len)
        far = SEP_TAB_OUT + sheet_w  # inner edge of the far tab
        SEP_CACHE[key] = trimesh.boolean.union(
            [
                box((SEP_TAB_OUT, far), (0, sheet_l), (0, SEP_T)),
                box((0, SEP_TAB_OUT), tab_y, (0, SEP_T)),
                box((far, far + SEP_TAB_OUT), tab_y, (0, SEP_T)),
            ]
        )
    return SEP_CACHE[key]


print("=" * 60)
print(f"Card Holder Generator -- {CFG['game']['name']}")
print("=" * 60)
print("Build")
print(f"  thickness   {T} mm walls, {F} mm floor")
if SLEEVE:
    print(f"  sleeve      {SLEEVE[0]} x {SLEEVE[1]} mm unless a variant states its own")
else:
    print("  sleeve      whatever each variant states, if any")
print(f"  clearance   {CLEAR} mm the cavity must have over the sleeve")
print("Separator")
print(f"  sheet       {SEP_T} mm thick, cavity less {SEP_FIT} mm for the fit")
print(f"  tabs        {SEP_TAB_OUT} mm out each side, filling the variant's")
print(f"              side opening less the same {SEP_FIT} mm")
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} card_holders.variants.{name}"
    W, L, H = dims(need(spec, "size", at), 3, at, "size")
    corner = need(spec, "corner", at)
    pack_axis = need(spec, "pack_axis", at)
    pack_count = need(spec, "pack_count", at)
    n_sep = spec.get("separators", 0)

    INNER_W = W - 2 * T
    INNER_L = L - 2 * T
    depth = H - F  # what is left over the floor is the card stack

    SHEET_W = INNER_W - SEP_FIT
    SHEET_L = INNER_L - SEP_FIT
    SEP_W = SHEET_W + 2 * SEP_TAB_OUT  # separator width over the tabs

    if pack_axis not in ("L", "W"):
        raise ValueError(f"[{name}] pack_axis must be 'L' or 'W', got {pack_axis!r}")
    if INNER_W <= 0 or INNER_L <= 0 or depth <= 0:
        raise ValueError(
            f"[{name}] outside {W} x {L} x {H} mm leaves nothing inside "
            f"{T} mm walls and a {F} mm floor"
        )
    if not T <= corner < L / 2:
        raise ValueError(
            f"[{name}] corner must be in [{T}, {L / 2}) to leave posts and an "
            f"opening between them, got {corner}"
        )

    sleeve = sleeve_of(spec, at)
    if sleeve and (
        INNER_W + 1e-9 < sleeve[0] + CLEAR or INNER_L + 1e-9 < sleeve[1] + CLEAR
    ):
        raise ValueError(
            f"[{name}] the {INNER_W} x {INNER_L} mm cavity is too small for a "
            f"{sleeve[0]} x {sleeve[1]} mm sleeve with {CLEAR} mm clearance, "
            f"which needs {sleeve[0] + CLEAR} x {sleeve[1] + CLEAR} mm -- grow "
            f"the outside size or thin the walls"
        )

    # The tab fills the side opening bar the fit, so it is as long as the
    # posts allow and always clears them: nothing to configure, nothing to
    # keep in step when the corner changes.
    OPENING = L - 2 * corner
    SEP_TAB_LEN = OPENING - SEP_FIT

    if n_sep and SEP_TAB_LEN <= 0:
        raise ValueError(
            f"[{name}] the {OPENING} mm side opening is no wider than the "
            f"{SEP_FIT} mm separator fit, leaving no tab -- shorten the corner posts"
        )
    if n_sep * SEP_T >= depth:
        raise ValueError(
            f"[{name}] {n_sep} separators are {n_sep * SEP_T} mm of a "
            f"{depth} mm stack, leaving no room for cards"
        )

    row_w = pack_count * W if pack_axis == "W" else W
    row_l = pack_count * L if pack_axis == "L" else L
    over = 2.0  # overshoot so cuts clear the outer faces

    mesh = trimesh.boolean.difference(
        [
            box((0, W), (0, L), (0, H)),  # solid blank
            box((T, W - T), (T, L - T), (F, H + over)),  # card cavity
            # Take out both long walls between the corner posts. The span
            # between them is already cavity, so one cut does both sides.
            box((-over, W + over), (corner, L - corner), (F, H + over)),
        ]
    )
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_card_holder_{name}.stl"
    mesh.export(path)

    sep_stack = n_sep * SEP_T
    card_stack = depth - sep_stack

    print("-" * 60)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm")
    print(f"    inside    {INNER_W} x {INNER_L} mm, {depth} mm deep")
    if sleeve:
        print(
            f"    sleeve    {sleeve[0]} x {sleeve[1]} mm + {CLEAR} mm clearance -> "
            f"{INNER_W - sleeve[0] - CLEAR:.1f} / {INNER_L - sleeve[1] - CLEAR:.1f} "
            f"mm to spare{'' if 'sleeve' not in spec else '   (this variant only)'}"
        )
    print(
        f"    packing   {pack_count} repeated along {pack_axis} -> "
        f"{row_w:.1f} x {row_l:.1f} mm row"
    )
    print("  Long sides")
    print(f"    posts     {corner} mm at each corner, full height, {T} mm thick")
    print(f"    opening   {OPENING} mm long, floor to rim ({depth} mm tall)")
    if sleeve:
        trapped = OPENING < sleeve[1]
        print(
            f"    check     {OPENING} mm opening vs {sleeve[1]} mm card -> "
            f"{'OK, card cannot slide out' if trapped else 'CARD CAN ESCAPE'}"
        )
    else:
        print("    check     no sleeve stated, so nothing to check the opening against")
    print("  Mesh checks")
    report_mesh(mesh)
    if n_sep:
        sep_path = f"{OUTDIR}/{GAME_ID}_card_separator_{name}.stl"
        separator(SHEET_W, SHEET_L, SEP_TAB_LEN).export(sep_path)
        print("  Separators")
        if abs(SEP_W - W) < 1e-6:
            sits = "flush"
        else:
            sits = "proud" if SEP_W > W else "recessed"
        print(f"    sheet     {SHEET_W:.1f} x {SHEET_L:.1f} mm, {SEP_T} mm thick")
        print(f"    overall   {SEP_W:.1f} mm wide vs {W} mm holder -> {sits}")
        print(f"    print     {n_sep}, {sep_stack:.1f} mm of the stack")
        print(
            f"    tabs      {SEP_TAB_LEN:.1f} mm in the {OPENING} mm opening -> "
            f"{SEP_FIT} mm of play"
        )

    print("  Capacity")
    print(
        f"    stack     {depth} mm less {sep_stack:.1f} mm of separators -> "
        f"{card_stack:.1f} mm of cards"
    )
    print(f"    ~{card_stack / CARD_THICK:.0f} sleeved cards + {n_sep} separators")
    print(f"  -> {path}")
    if n_sep:
        print(f"  -> {sep_path}")
    print()
