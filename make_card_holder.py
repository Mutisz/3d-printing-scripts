"""
Card holders: top-loaded tray, open top, open long sides.

Cards lie flat and stack upward, dropped in through the open top. The floor
and the two short end walls are solid and full height. The two long walls
are gone but for a short fragment at each corner -- four posts that leave
the long sides open to reach in from. How much wall each post keeps is
corner, and unless the variant states one it is 20% of the length at each
end, leaving the middle 60% of each long side open.

Those openings are shorter than a card's 91 mm length, so the corner posts
block a card from sliding straight out sideways; it would have to rotate
first. Access without escape.

A holder can be labelled: emboss raises text off the cavity floor, under
where the cards sit, so a holder still says what deck it is for once it is
out of the box and empty. It is the same option a tray compartment takes,
and every separator takes it too -- which is the point of naming them, as
a sheet reading AGE II is worth more than a sheet.

Separators are named, not counted. Each id is one sheet and one STL, and
each says only what it wants of its own: thickness, fit, tab_out, a label,
or nothing at all.

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
from label import emboss_solid

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
#
# These are the numbers every sheet takes unless it states its own, so a
# variant can slip one thicker or looser divider in among the rest.
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


def separator(sheet_w, sheet_l, tab_len, thick, tab_out):
    """Flat sheet with a tab each side, laid out print-ready on the bed."""
    key = (sheet_w, sheet_l, tab_len, thick, tab_out)
    if key not in SEP_CACHE:
        tab_y0 = (sheet_l - tab_len) / 2
        tab_y = (tab_y0, tab_y0 + tab_len)
        far = tab_out + sheet_w  # inner edge of the far tab
        parts = [box((tab_out, far), (0, sheet_l), (0, thick))]
        if tab_out > 0:  # a sheet asked to sit flush has no tabs to build
            parts += [
                box((0, tab_out), tab_y, (0, thick)),
                box((far, far + tab_out), tab_y, (0, thick)),
            ]
        SEP_CACHE[key] = trimesh.boolean.union(parts) if len(parts) > 1 else parts[0]
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
    corner = spec.get("corner")
    if corner is None:
        corner = 0.2 * L  # posts down 20% of each long wall, the middle 60% open
    seps = spec.get("separators") or {}
    if not isinstance(seps, dict):
        raise ValueError(
            f"[{name}] separators must be an object keyed by separator id, got "
            f"{seps!r} -- one entry per sheet, each stating whatever it wants "
            f"of its own and taking the section's numbers for the rest"
        )

    INNER_W = W - 2 * T
    INNER_L = L - 2 * T
    depth = H - F  # what is left over the floor is the card stack

    if INNER_W <= 0 or INNER_L <= 0 or depth <= 0:
        raise ValueError(
            f"[{name}] outside {W} x {L} x {H} mm leaves nothing inside "
            f"{T} mm walls and a {F} mm floor"
        )
    if not T <= corner < L / 2:
        raise ValueError(
            f"[{name}] corner must be in [{T}, {L / 2}) to leave posts and an "
            f"opening between them, got {corner:.1f}"
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

    sheets = []
    for sid, sheet_spec in seps.items():
        seat = f"{at} separators.{sid}"
        if sheet_spec is None:  # a bare null reads as "nothing of my own"
            sheet_spec = {}
        if not isinstance(sheet_spec, dict):
            raise ValueError(f"{seat}: must be an object, got {sheet_spec!r}")
        if not sid or "/" in sid or "\\" in sid:
            raise ValueError(
                f"{at} separators: {sid!r} will not do as an id -- it names an "
                f"STL, so it cannot be empty or carry a path separator"
            )

        thick = sheet_spec.get("thickness", SEP_T)
        fit = sheet_spec.get("fit", SEP_FIT)
        tab_out = sheet_spec.get("tab_out", SEP_TAB_OUT)
        if tab_out is None:  # null means "land flush with the outer wall"
            tab_out = T

        if thick <= 0 or fit < 0 or tab_out < 0:
            raise ValueError(
                f"{seat}: thickness must be positive and fit and tab_out cannot "
                f"be negative, got {thick}, {fit} and {tab_out}"
            )

        sheet_w, sheet_l = INNER_W - fit, INNER_L - fit
        tab_len = OPENING - fit
        if sheet_w <= 0 or sheet_l <= 0:
            raise ValueError(
                f"{seat}: a {fit} mm fit leaves no sheet inside the "
                f"{INNER_W} x {INNER_L} mm cavity"
            )
        if tab_len <= 0:
            raise ValueError(
                f"{seat}: the {OPENING:.1f} mm side opening is no wider than the "
                f"{fit} mm fit, leaving no tab -- shorten the corner posts"
            )

        mesh_sep = separator(sheet_w, sheet_l, tab_len, thick, tab_out)
        sheet_label = None
        if sheet_spec.get("emboss"):
            # Onto the face of the sheet, which is the only surface a
            # separator has: the tabs are a wall thick and hold nothing.
            solid, sheet_label = emboss_solid(
                sheet_spec["emboss"],
                (tab_out, tab_out + sheet_w),
                (0, sheet_l),
                thick,
                f"{seat} emboss",
            )
            mesh_sep = trimesh.boolean.union([mesh_sep, solid])

        sheets.append(
            {
                "id": sid,
                "mesh": mesh_sep,
                "thick": thick,
                "w": sheet_w,
                "l": sheet_l,
                "tab": tab_len,
                "over": sheet_w + 2 * tab_out,  # width over the tabs
                "label": sheet_label,
            }
        )

    sep_stack = sum(sheet["thick"] for sheet in sheets)
    if sep_stack >= depth:
        raise ValueError(
            f"[{name}] {len(sheets)} separators are {sep_stack:.1f} mm of a "
            f"{depth} mm stack, leaving no room for cards"
        )

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
    label = spec.get("emboss")
    if label:  # onto the cavity floor, after it has been milled out
        solid, label_info = emboss_solid(
            label, (T, W - T), (T, L - T), F, f"{at} emboss"
        )
        mesh = trimesh.boolean.union([mesh, solid])
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_card_holder_{name}.stl"
    mesh.export(path)

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
    print("  Long sides")
    print(f"    posts     {corner:.1f} mm at each corner, full height, {T} mm thick")
    print(f"    opening   {OPENING:.1f} mm long, floor to rim ({depth} mm tall)")
    if sleeve:
        trapped = OPENING < sleeve[1]
        print(
            f"    check     {OPENING:.1f} mm opening vs {sleeve[1]} mm card -> "
            f"{'OK, card cannot slide out' if trapped else 'CARD CAN ESCAPE'}"
        )
    else:
        print("    check     no sleeve stated, so nothing to check the opening against")
    if label:
        text, size, stroke, height, along, drawn_w, drawn_h = label_info
        print("  Label")
        print(f"    text      {text}")
        print(
            f"    letters   {size:.1f} mm cap, {stroke:.2f} mm stroke, "
            f"{height:.2f} mm proud of the floor"
        )
        print(
            f"    drawn     {drawn_w:.1f} x {drawn_h:.1f} mm, running along {along}"
        )
    print("  Mesh checks")
    report_mesh(mesh)
    sep_paths = []
    if sheets:
        print("  Separators")
        print(
            f"    {'id':<14}{'thick':>6}{'sheet':>16}{'tab':>7}{'over tabs':>17}"
            f"  label"
        )
        for sheet in sheets:
            over = sheet["over"]
            sits = "flush"
            if abs(over - W) > 1e-6:
                sits = "proud" if over > W else "recessed"
            footprint = f"{sheet['w']:.1f} x {sheet['l']:.1f}"
            fits = f"{over:.1f} {sits}"
            text = sheet["label"][0] if sheet["label"] else "--"
            print(
                f"    {sheet['id']:<14}{sheet['thick']:>6.1f}{footprint:>16}"
                f"{sheet['tab']:>7.1f}{fits:>17}  {text}"
            )
            if sheet["label"]:
                text, size, stroke, height, along, _, _ = sheet["label"]
                print(
                    f"    {'':<14}{size:.1f} mm cap, {stroke:.2f} mm stroke, "
                    f"{height:.2f} mm proud, along {along}"
                )
            sep_path = f"{OUTDIR}/{GAME_ID}_card_separator_{name}_{sheet['id']}.stl"
            sheet["mesh"].export(sep_path)
            sep_paths.append(sep_path)

    print("  Capacity")
    print(
        f"    stack     {depth} mm less {sep_stack:.1f} mm of separators -> "
        f"{card_stack:.1f} mm of cards"
    )
    print(
        f"    ~{card_stack / CARD_THICK:.0f} sleeved cards + "
        f"{len(sheets)} separators"
    )
    print(f"  -> {path}")
    for sep_path in sep_paths:
        print(f"  -> {sep_path}")
    print()
