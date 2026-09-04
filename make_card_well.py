"""
Card wells: top-loaded tray, open top, open at one end.

Cards lie flat and stack upward, dropped in through the open top. The
floor is solid, and so are three of the four walls: both long walls and
one of the two short ones. The fourth wall -- the other short one -- is
gone but for a short fragment at each corner, two posts that leave the
middle of that end open to reach in from. How much wall each post keeps
is corner, a fraction of that wall's own length rather than a length in
mm, so the posts hold their proportion whatever size the variant is:
unless one is stated it is 0.2, a fifth of the wall at each end, leaving
the middle 60% open. State it once on the section and every variant
takes it unless it says otherwise.

That opening is narrower than a card's W, so the corner posts block a
card from sliding straight out; it would have to rotate first. Access
without escape.

A well can be labelled: emboss puts text on the cavity floor, under
where the cards sit -- raised off it, or cut into it if the label states
a depth, so a well still says what deck it is for once it is out of the
box and empty. It is the same option a tray compartment takes, and every
separator takes it too -- which is the point of naming them, as a sheet
reading AGE II is worth more than a sheet.

Separators are named, not counted. Each id is one sheet and one STL, and
each says only what it wants of its own: thickness, fit, tab_out, a
label, or nothing at all. Its one tab reaches out through the well's
open end, as long as that opening allows less the same fit that shrinks
the sheet -- nothing to configure, nothing to keep in step when corner
changes.

Wells stack badly left open: the top of one is nearly all cavity mouth,
so the one set on it drops a corner in. A lid closes that. It is the
separator sheet again, carrying a tab at the closed end that drops into
a notch cut down from the rim of that wall, holding it there rather than
loose on the cards, and a second tab at the open end that fills what is
left of that rim, landing in the opening itself. State the lid block and
every variant gets one, since the notch is cut into the well and a game
that stacks one well stacks them all; a variant says false to go
without.

A lid takes the well's own label unless it states another, which puts
the deck's name where a stack shows it instead of on the cavity floor,
which only an empty well shows. Cut in, not raised: letters standing
proud of a lid are what the well above would rock on.

A variant is stated by its outside dimensions, as a tray is: what has to
fit the game box is the hard constraint, and the cavity is what is left
inside the walls. Nothing under validation sizes any of that: the
sleeve, the clearance it wants and the card thickness only ever check
the cavity the size already decided, or estimate what will stack in it.
State them once for the section, override any of them on a variant
taking a different card, or leave them out and the same well is built
unchecked.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_card_well.py <game_id>
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
from label import emboss_defaults, emboss_solid

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

# Emptied before anything is read, so dropping the section from the file
# clears the wells it used to build rather than stranding them.
OUTDIR = outdir(GAME_ID, "card_wells")

WELLS = CFG.get("card_wells")
if not WELLS:  # an ordinary state, not an error: exit clean so runners can tell
    print(f"{WHERE}: no 'card_wells' section, nothing to build")
    raise SystemExit(0)

T = need(WELLS, "wall", WHERE)
F = need(WELLS, "floor", WHERE)
VARIANTS = need(WELLS, "variants", WHERE)
EMB = emboss_defaults(WELLS, f"{WHERE} card_wells")  # for wells and sheets

VALID = validation(WELLS, f"{WHERE} card_wells")

# The section's own corner, taken as every variant's default so a game
# whose wells all want the same post proportion states it once instead of
# on each one. A variant that disagrees still says so itself.
SECTION_CORNER = WELLS.get("corner")

# Separators: a flat sheet the full size of the cavity, so it stands proud
# of the cards and is easy to catch. A tab reaches out through the well's
# one open end, showing the split from outside the well. The tab is as
# long as that opening allows, so it is not configured: it follows the
# variant's corner posts, less the same fit as the sheet.
#
# These are the numbers every sheet takes unless it states its own, so a
# variant can slip one thicker or looser divider in among the rest.
SEP = need(WELLS, "separator", WHERE)
SEP_T = need(SEP, "thickness", f"{WHERE} separator")
SEP_FIT = need(SEP, "fit", f"{WHERE} separator")
SEP_TAB_OUT = SEP.get("tab_out")
if SEP_TAB_OUT is None:  # null means "land flush with the outer wall"
    SEP_TAB_OUT = T

SHEET_CACHE = {}  # variants sharing a cavity share one sheet, so build it once

# The lid, which is that sheet once more with a tab at the closed end too.
# Stating this block is what turns lids on, and it turns them on for the
# whole section: the notch that tab sits in is cut into the well, so it is
# not something one variant decides for itself without saying so.
#
# Its two fits pull opposite ways. Side to side the notch only has to locate
# the tab, and slop there is invisible; but a tab pinched in a tight notch
# stops short of its seat and leaves the lid standing proud, which is the one
# thing a stacking lid must not do. So the notch is cut wide and seated close.
LID = WELLS.get("lid")
LID_KEYS = ("thickness", "fit", "notch", "notch_fit", "seat", "emboss")
LID_NOTCH = 0.3  # of the closed end wall the tab takes, as corner is of W
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
    lid_keys(LID, f"{WHERE} card_wells")
    need(LID, "thickness", f"{WHERE} card_wells.lid")


def lid_of(spec, at):
    """The lid a variant gets, or None if it goes without one.

    The section's numbers under the variant's own word, and the well's
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
            f"stated once for the whole section, in card_wells.lid"
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
            f"{at} lid: notch is the fraction of the closed end wall the tab "
            f"takes, so it must be in (0, 1), got {notch}"
        )

    # The well's words, and the lid's over them. Saying which way the
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
        # a lid may say only how deep to cut the well's own name.
        "own_label": "text" in (mine or {}),
    }


def tabbed_sheet(sheet_w, sheet_l, tab_len, thick, tab_out, notch_w=0.0):
    """Flat sheet with a tab out the open end, laid out print-ready on the bed.

    A separator's whole story: one tab, reaching out through the well's one
    open end. A lid carries a second, narrower tab at the other end instead
    -- `notch_w` -- to seat in the notch cut there; nothing else tells the
    two apart.
    """
    key = (sheet_w, sheet_l, tab_len, thick, tab_out, notch_w)
    if key not in SHEET_CACHE:
        y0 = tab_out if notch_w else 0.0  # room at the closed end for its tab
        top = y0 + sheet_l  # far edge of the sheet
        parts = [box((0, sheet_w), (y0, top), (0, thick))]
        if tab_out > 0:  # a sheet asked to sit flush has no tab to build
            tx0 = (sheet_w - tab_len) / 2
            parts.append(
                box((tx0, tx0 + tab_len), (top, top + tab_out), (0, thick))
            )
        if notch_w:
            nx0 = (sheet_w - notch_w) / 2
            parts.append(box((nx0, nx0 + notch_w), (0, y0), (0, thick)))
        SHEET_CACHE[key] = trimesh.boolean.union(parts) if len(parts) > 1 else parts[0]
    return SHEET_CACHE[key]


print("=" * 60)
print(f"Card Well Generator -- {CFG['game']['name']}")
print("=" * 60)
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} card_wells.variants.{name}"
    W, L, H = dims(need(spec, "size", at), 3, at, "size")
    corner = spec.get("corner", SECTION_CORNER)
    if corner is None:
        corner = 0.2  # posts a fifth of the open end, leaving the middle 60% open
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
            f"[{name}] corner is the fraction of the open end's own wall each "
            f"post keeps, so it must be in (0, 0.5) to leave posts and an "
            f"opening between them, got {corner}"
        )
    post = corner * W  # what that fraction comes to on this variant
    if post < T:
        raise ValueError(
            f"[{name}] corner {corner} of a {W} mm wall leaves a {post:.1f} mm "
            f"post, narrower than the {T} mm wall it stands in -- state at "
            f"least {math.ceil(T / W * 1000) / 1000}"
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

    # The tab fills the end opening bar the fit, so it is as wide as the
    # posts allow and always clears them: nothing to configure, nothing to
    # keep in step when the corner changes.
    OPENING = W - 2 * post

    # An opening no shorter than the card is a well that cannot hold it:
    # the card slides straight out the end it was meant to be reached in.
    if sleeve and OPENING + 1e-9 >= sleeve[0]:
        keep = math.floor((W - sleeve[0]) / (2 * W) * 1000) / 1000 + 0.001
        raise ValueError(
            f"[{name}] corner {corner} leaves a {OPENING:.1f} mm end opening, "
            f"no shorter than the {sleeve[0]} mm card it has to keep in, so "
            f"the card can slide out -- state a corner of at least {keep:g}, "
            f"or shorten W"
        )

    # The lid's own numbers on this variant. The notch has to stay inside
    # the cavity: run it out to the corners and it would cut the tops off
    # the closed end wall's own corners.
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
                f"the closed end's own corners"
            )
        if lid_w <= 0 or lid_l <= 0 or lid_tab_len <= 0:
            raise ValueError(
                f"[{name}] a {lid['fit']} mm lid fit leaves no sheet in the "
                f"{INNER_W} x {INNER_L} mm cavity, or no tab in its "
                f"{OPENING:.1f} mm end opening"
            )
        if lid_tab_w > lid_w:
            raise ValueError(
                f"[{name}] a {lid_tab_w:.1f} mm notch tab is wider than the "
                f"{lid_w:.1f} mm sheet it hangs off"
            )
        if lid_tab_w < T:
            raise ValueError(
                f"[{name}] a lid notch of {lid['notch']} on a {W} mm wall, less "
                f"{lid['notch_fit']} mm of notch_fit, leaves a {lid_tab_w:.1f} mm "
                f"notch tab, thinner than the {T} mm wall it seats in -- state at "
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
                f"{seat}: the {OPENING:.1f} mm end opening is no wider than the "
                f"{fit} mm fit, leaving no tab -- shorten the corner posts"
            )

        mesh_sep = tabbed_sheet(sheet_w, sheet_l, tab_len, thick, tab_out)
        sheet_label = None
        if sheet_spec.get("emboss"):
            # Onto the face of the sheet, which is the only surface a
            # separator has: the tab is a wall thick and holds nothing.
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

        sheets.append(
            {
                "id": sid,
                "mesh": mesh_sep,
                "thick": thick,
                "w": sheet_w,
                "l": sheet_l,
                "tab": tab_len,
                "over": sheet_l + tab_out,  # length over the tab
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
        # Take the closed-end wall's opposite wall out between the corner
        # posts -- the one open end this well has.
        box((post, W - post), (L - T - over, L + over), (F, H + over)),
    ]
    if lid:
        # Down from the rim, so nothing here is printed over air: what is
        # left under the cut is the shoulder the lid comes to rest on. Only
        # the closed end needs a notch -- the open end's rim is already the
        # opening the lid's other tab lands in.
        nx0, nx1 = (W - notch_w) / 2, (W + notch_w) / 2
        cuts.append(box((nx0, nx1), (-over, T + over), (H - lid_down, H + over)))
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
    path = f"{OUTDIR}/{GAME_ID}_card_well_{name}.stl"
    mesh.export(path)

    lid_label = None
    if lid:
        # The open-end tab is not the lid's to shorten: it is what fills
        # the rim over that opening, and a rim with a gap in it is the hole
        # this whole part exists to close. So it reaches a wall out, as a
        # separator's does by default.
        mesh_lid = tabbed_sheet(
            lid_w, lid_l, lid_tab_len, lid["thickness"], T, lid_tab_w
        )
        if lid["label"]:
            solid, lid_label = emboss_solid(
                lid["label"],
                (0, lid_w),
                (T, T + lid_l),
                lid["thickness"],
                f"{at} lid emboss",
                EMB,
            )
            if not lid_label["cut"]:
                raise ValueError(
                    f"{at} lid emboss: letters standing {lid_label['amount']} mm "
                    f"proud of a lid are what the next well up would rock on "
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

    lid_path = None
    if lid:
        lid_path = f"{OUTDIR}/{GAME_ID}_card_lid_{name}.stl"
        mesh_lid.export(lid_path)
    sep_paths = []
    for sheet in sheets:
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
