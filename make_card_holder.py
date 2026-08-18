"""
Card holders: top-loaded tray, open top, open long sides.

Cards lie flat and stack upward, dropped in through the open top. The floor
and the two short end walls are solid and full height. The two long walls
are gone but for a short fragment at each corner -- four posts that leave
the long sides open to reach in from. How much wall each post keeps is
corner, a fraction of that wall rather than a length in mm, so the posts
hold their proportion whatever size the variant is: unless one is stated
it is 0.2, a fifth of the length at each end, leaving the middle 60% of
each long side open.

Those openings are shorter than a card's 91 mm length, so the corner posts
block a card from sliding straight out sideways; it would have to rotate
first. Access without escape.

A holder can be labelled: emboss puts text on the cavity floor, under
where the cards sit -- raised off it, or cut into it if the label states a
depth, so a holder still says what deck it is for once it is
out of the box and empty. It is the same option a tray compartment takes,
and every separator takes it too -- which is the point of naming them, as
a sheet reading AGE II is worth more than a sheet.

Separators are named, not counted. Each id is one sheet and one STL, and
each says only what it wants of its own: thickness, fit, tab_out, a label,
or nothing at all.

Holders stack badly left open: the top of one is nearly all cavity mouth,
so the one set on it drops a corner in. A lid closes that. It is the
separator sheet again, carrying a tab at each end that drops into a notch
cut down from the rim of the end walls, which holds it there rather than
loose on the cards. Its side tabs -- the pair a separator wears to be
caught by -- land in the side openings and fill the last of the rim, so a
lidded holder tops out as a solid rectangle with nothing left to fall
into. State the lid block and every variant gets one, since the notch is
cut into the holder and a game that stacks one holder stacks them all; a
variant says false to go without.

A lid takes the holder's own label unless it states another, which puts
the deck's name where a stack shows it instead of on the cavity floor,
which only an empty holder shows. Cut in, not raised: letters standing
proud of a lid are what the holder above would rock on.

A variant is stated by its outside dimensions, as a tray is: what has to
fit the game box is the hard constraint, and the cavity is what is left
inside the walls. Nothing under validation sizes any of that: the sleeve,
the clearance it wants and the card thickness only ever check the cavity
the size already decided, or estimate what will stack in it. State them
once for the section, override any of them on a variant taking a different
card, or leave them out and the same holder is built unchecked.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_card_holder.py <game_id>
"""

import math

import trimesh

from gameconfig import box, load_game, need, outdir, parse_game_id, report_mesh
from label import emboss_defaults, emboss_solid

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
VARIANTS = need(HOLDERS, "variants", WHERE)
EMB = emboss_defaults(HOLDERS, f"{WHERE} card_holders")  # for holders and sheets

# Nothing here builds anything. A sleeve is what the cavity is checked
# against, clearance how much bigger than it the cavity has to come out, and
# card_thickness what the capacity estimate counts in -- so a section states
# them for every variant, a variant overrides the ones it disagrees with,
# and a holder with none stated comes out exactly the same, just unchecked.
VAL_KEYS = ("sleeve", "clearance", "card_thickness")


def validation(spec, at):
    """The validation block a section or a variant states.

    Closed to those three keys: this block is inherited silently, so a typo
    in it would otherwise turn a check off without ever saying so.
    """
    block = spec.get("validation") or {}
    if not isinstance(block, dict):
        raise ValueError(f"{at} validation: must be an object, got {block!r}")
    unknown = [key for key in block if key not in VAL_KEYS]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{at} validation: {named} is not something a holder is checked "
            f"against -- it takes {', '.join(VAL_KEYS)}"
        )
    stray = [key for key in VAL_KEYS if key in spec]
    if stray:
        named = ", ".join(repr(key) for key in stray)
        raise ValueError(
            f"{at}: {named} goes inside validation, not beside it -- left out "
            f"here it would be read as nothing at all, quietly dropping the "
            f"check it was written for"
        )
    return block


VALID = validation(HOLDERS, f"{WHERE} card_holders")

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

SHEET_CACHE = {}  # variants sharing a cavity share one sheet, so build it once

# The lid, which is that sheet once more with an end tab each side. Stating
# this block is what turns lids on, and it turns them on for the whole
# section: the notch an end tab sits in is cut into the holder, so it is not
# something one variant decides for itself without saying so.
#
# Its two fits pull opposite ways. Side to side the notch only has to locate
# the tab, and slop there is invisible; but a tab pinched in a tight notch
# stops short of its seat and leaves the lid standing proud, which is the one
# thing a stacking lid must not do. So the notch is cut wide and seated close.
LID = HOLDERS.get("lid")
LID_KEYS = ("thickness", "fit", "notch", "notch_fit", "seat", "emboss")
LID_NOTCH = 0.3  # of the end wall each end tab takes, as corner is of L
LID_NOTCH_FIT = 0.6  # how much wider than its tab the notch is cut, in all
LID_SEAT = 0.2  # how far under the rim the lid comes to rest


def lid_keys(block, at):
    """A lid block, closed to the keys a lid takes.

    Closed for the reason the validation block is: a section stating this
    hands every variant a lid without the variant saying a word, so a typo
    in it would come out as a lid quietly built on the defaults.
    """
    if not isinstance(block, dict):
        raise ValueError(f"{at} lid: must be an object, got {block!r}")
    unknown = [key for key in block if key not in LID_KEYS]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{at} lid: {named} is not something a lid takes -- it takes "
            f"{', '.join(LID_KEYS)}"
        )
    return block


if LID is not None:
    lid_keys(LID, f"{WHERE} card_holders")
    need(LID, "thickness", f"{WHERE} card_holders.lid")


def lid_of(spec, at):
    """The lid a variant gets, or None if it goes without one.

    The section's numbers under the variant's own word, and the holder's
    own label unless the lid states another -- naming the lid is the point
    of a lid you can read in a stack, and typing that name twice is not.
    """
    own = spec.get("lid", {} if LID else False)
    if own is True:  # sugar for "one of those, on the section's numbers"
        own = {}
    if own is False:
        return None
    if not isinstance(own, dict):
        raise ValueError(
            f"{at} lid: true for one on the section's numbers, false for none "
            f"at all, or an object stating what differs -- got {own!r}"
        )
    if LID is None:
        raise ValueError(
            f"{at} lid: nothing to build one from -- what a lid is made of is "
            f"stated once for the whole section, in card_holders.lid"
        )
    lid_keys(own, at)
    said = {**LID, **own}

    thick = said["thickness"]
    fit = said.get("fit", SEP_FIT)
    notch = said.get("notch", LID_NOTCH)
    notch_fit = said.get("notch_fit", LID_NOTCH_FIT)
    seat = said.get("seat", LID_SEAT)
    if thick <= 0 or fit < 0 or notch_fit < 0 or seat < 0:
        raise ValueError(
            f"{at} lid: thickness must be positive, and fit, notch_fit and "
            f"seat cannot be negative, got {thick}, {fit}, {notch_fit} and {seat}"
        )
    if not 0 < notch < 1:
        raise ValueError(
            f"{at} lid: notch is the fraction of the end wall each tab takes, "
            f"so it must be in (0, 1), got {notch}"
        )

    # The holder's words, and the lid's over them. Saying which way the
    # letters go overrides the other kind rather than colliding with it, the
    # way a label already overrides its section's default.
    label = dict(spec.get("emboss") or {})
    mine = said.get("emboss")
    if mine is not None:
        if not isinstance(mine, dict):
            raise ValueError(f"{at} lid emboss: must be an object, got {mine!r}")
        if "depth" in mine:
            label.pop("height", None)
        elif "height" in mine:
            label.pop("depth", None)
        label.update(mine)
    return {
        "thickness": thick,
        "fit": fit,
        "notch": notch,
        "notch_fit": notch_fit,
        "seat": seat,
        "label": label or None,
        # Whose words they are, which is not the same as who stated a block:
        # a lid may say only how deep to cut the holder's own name.
        "own_label": "text" in (mine or {}),
    }


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


def checks_of(spec, at):
    """What a variant is checked against: its own words over the section's.

    Every key is optional at either level, and a missing one is not an error
    -- it only means there is nothing to check that against. Returns the
    sleeve, the clearance, the card thickness, and the block the variant
    stated itself, which is what the report marks as its own.
    """
    own = validation(spec, at)
    checks = {**VALID, **own}

    sleeve = checks.get("sleeve")
    if sleeve is not None:
        sleeve = dims(sleeve, 2, at, "sleeve")

    clear = checks.get("clearance", 0.0)
    if clear < 0:
        raise ValueError(
            f"{at} validation: clearance is room demanded over the sleeve, so "
            f"it cannot be negative, got {clear}"
        )

    thick = checks.get("card_thickness")
    if thick is not None and thick <= 0:
        raise ValueError(
            f"{at} validation: card_thickness must be positive to estimate a "
            f"stack from, got {thick}"
        )
    return sleeve, clear, thick, own


def own_note(own, *keys):
    """Flag a report line whose numbers the variant overrode itself."""
    return "   (this variant only)" if any(key in own for key in keys) else ""


def tabbed_sheet(sheet_w, sheet_l, tab_len, thick, tab_out, end_tab=0.0):
    """Flat sheet with a tab each long side, laid out print-ready on the bed.

    A separator and a lid are the one part twice over: `end_tab` is how wide
    a tab it also carries at each end, to seat in the holder's notches, and
    no end tab at all is a separator.
    """
    key = (sheet_w, sheet_l, tab_len, thick, tab_out, end_tab)
    if key not in SHEET_CACHE:
        y0 = tab_out if end_tab else 0.0  # room at each end for those tabs
        top = y0 + sheet_l  # far edge of the sheet
        tab_y0 = y0 + (sheet_l - tab_len) / 2
        tab_y = (tab_y0, tab_y0 + tab_len)
        far = tab_out + sheet_w  # inner edge of the far tab
        parts = [box((tab_out, far), (y0, top), (0, thick))]
        if tab_out > 0:  # a sheet asked to sit flush has no tabs to build
            parts += [
                box((0, tab_out), tab_y, (0, thick)),
                box((far, far + tab_out), tab_y, (0, thick)),
            ]
        if end_tab:
            end_x0 = tab_out + (sheet_w - end_tab) / 2
            end_x = (end_x0, end_x0 + end_tab)
            parts += [
                box(end_x, (0, y0), (0, thick)),
                box(end_x, (top, top + tab_out), (0, thick)),
            ]
        SHEET_CACHE[key] = trimesh.boolean.union(parts) if len(parts) > 1 else parts[0]
    return SHEET_CACHE[key]


print("=" * 60)
print(f"Card Holder Generator -- {CFG['game']['name']}")
print("=" * 60)
print("Build")
print(f"  thickness   {T} mm walls, {F} mm floor")
print("Validation")
if VALID.get("sleeve"):
    said = VALID["sleeve"]
    print(f"  sleeve      {said[0]} x {said[1]} mm unless a variant states its own")
else:
    print("  sleeve      whatever each variant states, if any")
print(
    f"  clearance   {VALID.get('clearance', 0.0)} mm the cavity must have over "
    f"the sleeve"
)
if VALID.get("card_thickness"):
    print(f"  cards       {VALID['card_thickness']} mm each, for the capacity")
else:
    print("  cards       whatever each variant states, if any")
print("Separator")
print(f"  sheet       {SEP_T} mm thick, cavity less {SEP_FIT} mm for the fit")
print(f"  tabs        {SEP_TAB_OUT} mm out each side, filling the variant's")
print(f"              side opening less the same {SEP_FIT} mm")
if LID:
    print("Lid")
    print(
        f"  sheet       {LID['thickness']} mm thick, seating "
        f"{LID.get('seat', LID_SEAT)} mm under the rim"
    )
    print(
        f"  notches     {LID.get('notch', LID_NOTCH) * 100:g}% of each end wall, "
        f"cut {LID.get('notch_fit', LID_NOTCH_FIT)} mm wider than the tab in it"
    )
    print("  label       the holder's own, cut in, unless the lid states another")
    print("  every variant gets one unless it says lid false")
if EMB:
    print("Label")
    stated = ", ".join(f"{key} {value}" for key, value in EMB.items())
    print(f"  defaults    {stated}, unless a label says otherwise")
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} card_holders.variants.{name}"
    W, L, H = dims(need(spec, "size", at), 3, at, "size")
    corner = spec.get("corner")
    if corner is None:
        corner = 0.2  # posts down a fifth of each long wall, the middle 60% open
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
    if not 0 < corner < 0.5:
        raise ValueError(
            f"[{name}] corner is the fraction of the long wall each post keeps, "
            f"so it must be in (0, 0.5) to leave posts and an opening between "
            f"them, got {corner}"
        )
    post = corner * L  # what that fraction comes to on this variant
    if post < T:
        raise ValueError(
            f"[{name}] corner {corner} of a {L} mm wall leaves a {post:.1f} mm "
            f"post, narrower than the {T} mm wall it stands in -- state at "
            f"least {math.ceil(T / L * 1000) / 1000}"
        )

    sleeve, clear, card_thick, own_checks = checks_of(spec, at)
    if sleeve and (
        INNER_W + 1e-9 < sleeve[0] + clear or INNER_L + 1e-9 < sleeve[1] + clear
    ):
        raise ValueError(
            f"[{name}] the {INNER_W} x {INNER_L} mm cavity is too small for a "
            f"{sleeve[0]} x {sleeve[1]} mm sleeve with {clear} mm clearance, "
            f"which needs {sleeve[0] + clear} x {sleeve[1] + clear} mm -- grow "
            f"the outside size or thin the walls"
        )

    # The tab fills the side opening bar the fit, so it is as long as the
    # posts allow and always clears them: nothing to configure, nothing to
    # keep in step when the corner changes.
    OPENING = L - 2 * post

    # The lid's own numbers on this variant. The notch has to stay inside
    # the cavity: run it out to the corners and it would cut the tops off
    # the posts, which are the very bits holding the long sides up.
    lid = lid_of(spec, at)
    lid_down = 0.0  # how much off the top of the stack a seated lid takes
    if lid:
        lid_down = lid["thickness"] + lid["seat"]
        notch_w = lid["notch"] * W
        lid_w = INNER_W - lid["fit"]
        lid_l = INNER_L - lid["fit"]
        lid_tab_len = OPENING - lid["fit"]
        lid_tab_w = notch_w - lid["notch_fit"]
        if notch_w > INNER_W + 1e-9:
            raise ValueError(
                f"[{name}] a lid notch of {lid['notch']} comes to {notch_w:.1f} mm "
                f"on a {W} mm wall, wider than the {INNER_W} mm cavity it has to "
                f"stay inside -- state at most "
                f"{math.floor(INNER_W / W * 1000) / 1000}, or the notch eats into "
                f"the corner posts"
            )
        if lid_w <= 0 or lid_l <= 0 or lid_tab_len <= 0:
            raise ValueError(
                f"[{name}] a {lid['fit']} mm lid fit leaves no sheet in the "
                f"{INNER_W} x {INNER_L} mm cavity, or no tab in its "
                f"{OPENING:.1f} mm side opening"
            )
        if lid_tab_w > lid_w:
            raise ValueError(
                f"[{name}] a {lid_tab_w:.1f} mm end tab is wider than the "
                f"{lid_w:.1f} mm sheet it hangs off"
            )
        if lid_tab_w < T:
            raise ValueError(
                f"[{name}] a lid notch of {lid['notch']} on a {W} mm wall, less "
                f"{lid['notch_fit']} mm of notch_fit, leaves a {lid_tab_w:.1f} mm "
                f"end tab, thinner than the {T} mm wall it seats in -- state at "
                f"least {math.ceil((T + lid['notch_fit']) / W * 1000) / 1000}"
            )

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

        mesh_sep = tabbed_sheet(sheet_w, sheet_l, tab_len, thick, tab_out)
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
                EMB,
            )
            if sheet_label["cut"]:
                mesh_sep = trimesh.boolean.difference([mesh_sep, solid])
            else:
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
    if sep_stack + lid_down >= depth:
        taken = [f"{len(sheets)} separators are {sep_stack:.1f} mm"]
        if lid:
            taken.append(f"the lid seats {lid_down:.1f} mm down")
        raise ValueError(
            f"[{name}] {' and '.join(taken)} of a {depth} mm stack, leaving no "
            f"room for cards"
        )

    over = 2.0  # overshoot so cuts clear the outer faces

    cuts = [
        box((0, W), (0, L), (0, H)),  # solid blank
        box((T, W - T), (T, L - T), (F, H + over)),  # card cavity
        # Take out both long walls between the corner posts. The span
        # between them is already cavity, so one cut does both sides.
        box((-over, W + over), (post, L - post), (F, H + over)),
    ]
    if lid:
        # Down from the rim, so nothing here is printed over air: what is
        # left under the cut is the shoulder the lid comes to rest on.
        nx0, nx1 = (W - notch_w) / 2, (W + notch_w) / 2
        cuts += [
            box((nx0, nx1), (-over, T + over), (H - lid_down, H + over)),
            box((nx0, nx1), (L - T - over, L + over), (H - lid_down, H + over)),
        ]
    mesh = trimesh.boolean.difference(cuts)
    label = spec.get("emboss")
    if label:  # onto the cavity floor, after it has been milled out
        solid, label_info = emboss_solid(
            label, (T, W - T), (T, L - T), F, f"{at} emboss", EMB
        )
        if label_info["cut"]:
            mesh = trimesh.boolean.difference([mesh, solid])
        else:
            mesh = trimesh.boolean.union([mesh, solid])
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_card_holder_{name}.stl"
    mesh.export(path)

    lid_label = None
    if lid:
        # The side tabs are not the lid's to shorten: they are what fills
        # the rim over the side openings, and a rim with a gap in it is the
        # hole this whole part exists to close. So they reach a wall out,
        # as a separator's do by default.
        mesh_lid = tabbed_sheet(
            lid_w, lid_l, lid_tab_len, lid["thickness"], T, lid_tab_w
        )
        if lid["label"]:
            solid, lid_label = emboss_solid(
                lid["label"],
                (T, T + lid_w),
                (T, T + lid_l),
                lid["thickness"],
                f"{at} lid emboss",
                EMB,
            )
            if not lid_label["cut"]:
                raise ValueError(
                    f"{at} lid emboss: letters standing {lid_label['amount']} mm "
                    f"proud of a lid are what the next holder up would rock on "
                    f"-- state depth, on the lid or on the section, so the name "
                    f"is cut into it instead"
                )
            # Cleaned here rather than after, since an unlabelled lid is the
            # cached sheet itself and tidying that would tidy it for everyone.
            mesh_lid = trimesh.boolean.difference([mesh_lid, solid])
            mesh_lid.merge_vertices()
            mesh_lid.update_faces(mesh_lid.nondegenerate_faces())

    card_stack = depth - sep_stack - lid_down

    print("-" * 60)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm")
    print(f"    inside    {INNER_W} x {INNER_L} mm, {depth} mm deep")
    if sleeve:
        print(
            f"    sleeve    {sleeve[0]} x {sleeve[1]} mm + {clear} mm clearance -> "
            f"{INNER_W - sleeve[0] - clear:.1f} / {INNER_L - sleeve[1] - clear:.1f} "
            f"mm to spare{own_note(own_checks, 'sleeve', 'clearance')}"
        )
    print("  Long sides")
    print(
        f"    posts     {post:.1f} mm at each corner, {corner * 100:g}% of the "
        f"{L} mm wall, full height, {T} mm thick"
    )
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
        way = "into the floor" if label_info["cut"] else "proud of the floor"
        print("  Label")
        print(f"    text      {label_info['text']}")
        print(
            f"    letters   {label_info['size']:.1f} mm cap, "
            f"{label_info['stroke']:.2f} mm stroke, "
            f"{label_info['amount']:.2f} mm {way}"
        )
        print(
            f"    drawn     {label_info['w']:.1f} x {label_info['h']:.1f} mm, "
            f"running along {label_info['along']}"
        )
    print("  Mesh checks")
    report_mesh(mesh)
    lid_path = None
    if lid:
        print("  Lid")
        print(
            f"    sheet     {lid_w:.1f} x {lid_l:.1f} mm, "
            f"{lid['thickness']} mm thick"
        )
        print(
            f"    notches   {notch_w:.1f} mm wide, {lid_down:.1f} mm down from the "
            f"rim, one in each end wall"
        )
        print(
            f"    tabs      {lid_tab_w:.1f} mm into those, and {lid_tab_len:.1f} mm "
            f"out each side filling the openings"
        )
        print(
            f"    seats     {lid['seat']} mm under the rim, closing the top to a "
            f"solid {W} x {L} mm to stack on"
        )
        if lid_label:
            whose = " (its own)" if lid["own_label"] else " (the holder's)"
            print(f"    text      {lid_label['text']}{whose}")
            print(
                f"    letters   {lid_label['size']:.1f} mm cap, "
                f"{lid_label['stroke']:.2f} mm stroke, "
                f"{lid_label['amount']:.2f} mm into the lid, along "
                f"{lid_label['along']}"
            )
        lid_path = f"{OUTDIR}/{GAME_ID}_card_lid_{name}.stl"
        mesh_lid.export(lid_path)
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
            text = sheet["label"]["text"] if sheet["label"] else "--"
            print(
                f"    {sheet['id']:<14}{sheet['thick']:>6.1f}{footprint:>16}"
                f"{sheet['tab']:>7.1f}{fits:>17}  {text}"
            )
            if sheet["label"]:
                info = sheet["label"]
                way = "deep" if info["cut"] else "proud"
                print(
                    f"    {'':<14}{info['size']:.1f} mm cap, "
                    f"{info['stroke']:.2f} mm stroke, {info['amount']:.2f} mm "
                    f"{way}, along {info['along']}"
                )
            sep_path = f"{OUTDIR}/{GAME_ID}_card_separator_{name}_{sheet['id']}.stl"
            sheet["mesh"].export(sep_path)
            sep_paths.append(sep_path)

    print("  Capacity")
    less = f"{sep_stack:.1f} mm of separators"
    if lid:
        less += f" and {lid_down:.1f} mm under the lid"
    print(f"    stack     {depth} mm less {less} -> {card_stack:.1f} mm of cards")
    if card_thick:
        print(
            f"    ~{card_stack / card_thick:.0f} sleeved cards + "
            f"{len(sheets)} separators"
            f"{own_note(own_checks, 'card_thickness')}"
        )
    else:
        print(
            f"    {len(sheets)} separators, and no card thickness to estimate "
            f"a card count from"
        )
    print(f"  -> {path}")
    if lid_path:
        print(f"  -> {lid_path}")
    for sep_path in sep_paths:
        print(f"  -> {sep_path}")
    print()
