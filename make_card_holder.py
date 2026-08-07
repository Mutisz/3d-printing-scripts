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

Most games sleeve everything the same way, so the sleeve size is stated once
for the section; a variant holding a different card states its own and gets
its own shell and its own separators.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_card_holder.py <game_id>
"""

import trimesh

from gameconfig import box, load_game, need, outdir, parse_game_id, report_mesh

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

HOLDERS = CFG.get("card_holders")
if not HOLDERS:  # an ordinary state, not an error: exit clean so runners can tell
    print(f"{WHERE}: no 'card_holders' section, nothing to build")
    raise SystemExit(0)

CLEAR = need(HOLDERS, "clearance", WHERE)  # clearance between cards and walls
T = need(HOLDERS, "wall", WHERE)
F = need(HOLDERS, "floor", WHERE)
CARD_THICK = need(HOLDERS, "card_thickness", WHERE)
VARIANTS = need(HOLDERS, "variants", WHERE)

# The section-wide sleeve, used by every variant that does not name its own.
# Absent is fine as long as each variant does name one.
SLEEVE = HOLDERS.get("sleeve")

# Separators: a flat sheet the full size of the cavity, so it stands proud
# of the cards by CLEAR and is easy to catch. A tab each side reaches out
# through the open long side, showing the split from outside the holder.
# The tab is as long as that opening allows, so it is not configured: it
# follows the variant's corner posts, less the same fit as the sheet.
SEP = need(HOLDERS, "separator", WHERE)
SEP_T = need(SEP, "thickness", f"{WHERE} separator")
SEP_FIT = need(SEP, "fit", f"{WHERE} separator")
SEP_TAB_OUT = SEP.get("tab_out")
if SEP_TAB_OUT is None:  # null means "land flush with the outer wall"
    SEP_TAB_OUT = T

OUTDIR = outdir(GAME_ID)

SEP_CACHE = {}  # variants sharing a sleeve share one sheet, so build it once


def sleeve_of(spec, at):
    """The variant's own sleeve size, falling back to the section's."""
    size = spec.get("sleeve", SLEEVE)
    if size is None:
        raise SystemExit(
            f"{at}: no 'sleeve', and none at {WHERE} card_holders.sleeve to "
            f"fall back on"
        )
    try:
        width, length = (float(v) for v in size)
    except (TypeError, ValueError):
        raise SystemExit(f"{at}: sleeve must be [W, L] in mm, got {size!r}") from None
    if width <= 0 or length <= 0:
        raise SystemExit(f"{at}: sleeve must be positive, got {size!r}")
    return width, length


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
print(f"  clearance   {CLEAR} mm added to the sleeve to get the cavity")
if SLEEVE:
    print(f"  sleeve      {SLEEVE[0]} x {SLEEVE[1]} mm unless a variant states its own")
else:
    print("  sleeve      stated by every variant, no section default")
print("Separator")
print(f"  sheet       {SEP_T} mm thick, cavity less {SEP_FIT} mm for the fit")
print(f"  tabs        {SEP_TAB_OUT} mm out each side, filling the variant's")
print(f"              side opening less the same {SEP_FIT} mm")
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} card_holders.variants.{name}"
    depth, corner = need(spec, "depth", at), need(spec, "corner", at)
    pack_axis = need(spec, "pack_axis", at)
    pack_count = need(spec, "pack_count", at)
    n_sep = spec.get("separators", 0)

    SLEEVE_W, SLEEVE_L = sleeve_of(spec, at)
    INNER_W = SLEEVE_W + CLEAR
    INNER_L = SLEEVE_L + CLEAR
    W = INNER_W + 2 * T
    L = INNER_L + 2 * T

    SHEET_W = INNER_W - SEP_FIT
    SHEET_L = INNER_L - SEP_FIT
    SEP_W = SHEET_W + 2 * SEP_TAB_OUT  # separator width over the tabs

    if pack_axis not in ("L", "W"):
        raise ValueError(f"[{name}] pack_axis must be 'L' or 'W', got {pack_axis!r}")
    if not T <= corner < L / 2:
        raise ValueError(
            f"[{name}] corner must be in [{T}, {L / 2}) to leave posts and an "
            f"opening between them, got {corner}"
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

    H = F + depth
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

    trapped = OPENING < SLEEVE_L
    sep_stack = n_sep * SEP_T
    card_stack = depth - sep_stack

    print("-" * 60)
    print(f"[{name}]")
    print("  Dimensions")
    print(
        f"    sleeve    {SLEEVE_W} x {SLEEVE_L} mm + {CLEAR} mm clearance"
        f"{'' if 'sleeve' not in spec else '   (this variant only)'}"
    )
    print(f"    inside    {INNER_W} x {INNER_L} mm")
    print(f"    outside   {W} x {L} x {H} mm")
    print(f"    stack     {depth} mm deep")
    print(
        f"    packing   {pack_count} repeated along {pack_axis} -> "
        f"{row_w:.1f} x {row_l:.1f} mm row"
    )
    print("  Long sides")
    print(f"    posts     {corner} mm at each corner, full height, {T} mm thick")
    print(f"    opening   {OPENING} mm long, floor to rim ({depth} mm tall)")
    print(
        f"    check     {OPENING} mm opening vs {SLEEVE_L} mm card -> "
        f"{'OK, card cannot slide out' if trapped else 'CARD CAN ESCAPE'}"
    )
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
