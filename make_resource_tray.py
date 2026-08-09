"""
Resource trays: open-top boxes divided into a row of compartments.

Each tray is a solid blank with one cavity milled per compartment, so the
outside dimensions come out exactly as asked -- they are the hard constraint
when a tray has to drop into a game box insert. Compartments sit in a single
row running along either the L or the W axis, separated by dividers as thick
as the walls.

Give a compartment an absolute size along the split axis, or null to let it
share out whatever the fixed ones leave over. A compartment may also be
shallower than the tray, which raises its floor and makes small pieces
easier to pinch out.

A compartment that carries compartments of its own is subdivided in turn,
across the perpendicular axis -- so a row along L becomes columns along W,
and so on down. Nest as deep as you like to get grids and ragged layouts.
Depth is inherited: set it on a parent and every compartment under it is
that deep unless it says otherwise.

Any compartment can also ask for notches: rounded slots cut down from the
rim through a named wall, to get a fingertip under whatever is inside. Any
wall will do, dividers as much as outer walls -- naming a divider opens a
channel to the neighbour, which is why a notch stops short of the floor by
default. A notch takes nothing away below its own bottom edge, so all of
this still prints without supports.

Where a notch is not enough, an opening takes the whole wall out instead:
floor to rim, over the wall's whole length bar a post left standing at
each corner -- the open side of a card holder, in a tray. Those posts are
what keeps the contents from following your fingers out, so how long they
are is the one thing an opening is really configured by: corner, 20% of
the wall at each end unless stated, the same default a card holder takes.

Every dimension comes from games/<game_id>.json; see gameconfig for the
schema. Run as: python3 make_resource_tray.py <game_id>
"""

import math

import trimesh

from gameconfig import box, load_game, need, outdir, parse_game_id, report_mesh

SIDES = ("W-", "W+", "L-", "L+")  # low/high side on each axis

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)
WHERE = f"games/{GAME_ID}.json"

# Emptied before anything is read, so dropping the section from the file
# clears the trays it used to build rather than stranding them.
OUTDIR = outdir(GAME_ID, "trays")

TRAYS = CFG.get("trays")
if not TRAYS:  # an ordinary state, not an error: exit clean so runners can tell
    print(f"{WHERE}: no 'trays' section, nothing to build")
    raise SystemExit(0)

T = need(TRAYS, "wall", WHERE)  # wall and divider thickness
F = need(TRAYS, "floor", WHERE)
VARIANTS = need(TRAYS, "variants", WHERE)


def resolve_sizes(where, comps, span):
    """Absolute size per compartment, sharing `span` out among the nulls."""
    autos = [c for c in comps if c.get("size") is None]
    fixed = sum(c["size"] for c in comps if c.get("size") is not None)

    if not autos:
        if abs(fixed - span) > 1e-6:
            raise ValueError(
                f"{where}: compartments total {fixed:.1f} mm but {span:.1f} mm "
                f"is available -- adjust a size, change the outside dimension, "
                f"or set one size to null to absorb the difference"
            )
        return [c["size"] for c in comps]

    leftover = span - fixed
    if leftover <= 0:
        raise ValueError(
            f"{where}: fixed compartments already total {fixed:.1f} mm of the "
            f"{span:.1f} mm available, leaving nothing for the {len(autos)} "
            f"sized null"
        )
    share = leftover / len(autos)
    return [share if c.get("size") is None else c["size"] for c in comps]


def wall_band(side, xr, yr):
    """The strip one wall of a rect occupies, measured across its thickness.

    The wall sits just outside the compartment on `side`, so the strip is
    that thickness plus an overshoot either way: outward it clears the tray
    face or the neighbour, inward it is already cavity.
    """
    over = 2.0
    edge = (xr if side in ("W-", "W+") else yr)[0 if side.endswith("-") else 1]
    if side.endswith("-"):
        return (edge - T - over, edge + over)
    return (edge - over, edge + T + over)


def wall_is_outer(side, xr, yr, W, L):
    """True when the named wall of a rect lands on the tray's own face."""
    low = side.endswith("-")
    pos = (xr if side.startswith("W") else yr)[0 if low else 1]
    limit = T if low else (W - T if side.startswith("W") else L - T)
    return abs(pos - limit) < 1e-6


def notch_cut(side, xr, yr, H, width, depth):
    """Rounded-bottom slot dropped from the rim through one wall of a rect.

    Nothing here overhangs. The slot removes material from the rim down, so
    what is left below it is simply a shorter wall -- printable as-is.
    """
    over = 2.0
    r = min(width / 2, depth)  # semicircular once the slot is deep enough
    z_bot = H - depth
    flat = width / 2 - r  # half-length of the straight-sided part, may be 0
    on_w = side in ("W-", "W+")

    band = wall_band(side, xr, yr)
    lo, hi = yr if on_w else xr
    mid = (lo + hi) / 2

    def place(across, along, zr):
        """Box in world axes, given ranges across and along the wall."""
        return box(across, along, zr) if on_w else box(along, across, zr)

    parts = [place(band, (mid - width / 2, mid + width / 2), (z_bot + r, H + over))]
    if flat > 1e-9:
        parts.append(place(band, (mid - flat, mid + flat), (z_bot, z_bot + r)))

    for offset in {-flat, flat}:  # a set, so a semicircle adds one cylinder
        cyl = trimesh.creation.cylinder(radius=r, height=band[1] - band[0], sections=64)
        # Stand the cylinder on the wall normal so the slot reads round in
        # the face of the wall, not in plan.
        cyl.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.pi / 2, [0, 1, 0] if on_w else [1, 0, 0]
            )
        )
        centre = [(band[0] + band[1]) / 2, mid + offset, z_bot + r]
        cyl.apply_translation(centre if on_w else [centre[1], centre[0], centre[2]])
        parts.append(cyl)

    return trimesh.boolean.union(parts)


def opening_cut(side, xr, yr, H, corner, depth):
    """One whole wall of a rect taken out, bar a post left at each corner.

    The card holder's open side, in a tray: rim to floor over the length of
    the wall, less `corner` mm at each end. Square-ended, because the posts
    are the whole point -- they are what the contents cannot get past, and
    rounding them would only make the gap between them longer.

    Like a notch it removes material downward from the rim and nothing under
    it, so what is left is a pair of short posts and the floor they stand
    on -- no overhang, no supports.
    """
    over = 2.0
    on_w = side in ("W-", "W+")
    band = wall_band(side, xr, yr)
    lo, hi = yr if on_w else xr
    along = (lo + corner, hi - corner)
    zr = (H - depth, H + over)
    return box(band, along, zr) if on_w else box(along, band, zr)


def plan(comps, split, W, L, H, where):
    """Divide the cavity into compartments, recursing into nested ones.

    Returns the cavity boxes to subtract from the blank, a flat record of what
    went where for the report -- (name, level, is_leaf, xr, yr, depth, z0) --
    and one row per notch and per opening cut.
    """
    over = 2.0  # overshoot so each cavity breaks through the top face
    cuts, placed, notched, opened = [], [], [], []

    def add_notches(comp, xr, yr, depth, where, label):
        """Cut each requested slot through the named wall of this rectangle."""
        for spec in comp.get("notches", []):
            side = need(spec, "side", where)
            if side not in SIDES:
                raise ValueError(
                    f"{where}: notch side must be one of {', '.join(SIDES)}, "
                    f"got {side!r}"
                )
            # The wall runs along the axis the side does not name.
            run = (yr[1] - yr[0]) if side.startswith("W") else (xr[1] - xr[0])

            width = spec.get("width")
            if width is None:
                width = 0.6 * run
            n_depth = spec.get("depth")
            if n_depth is None:
                n_depth = 0.5 * depth

            if not 0 < width <= run:
                raise ValueError(
                    f"{where}: notch width {width} must be in (0, {run:.1f}], "
                    f"the length of the {side} wall"
                )
            if not 0 < n_depth <= depth:
                raise ValueError(
                    f"{where}: notch depth {n_depth} must be in (0, {depth}], "
                    f"no deeper than the compartment it opens"
                )

            cuts.append(notch_cut(side, xr, yr, H, width, n_depth))
            notched.append(
                (
                    label,
                    side,
                    width,
                    n_depth,
                    min(width / 2, n_depth),
                    wall_is_outer(side, xr, yr, W, L),
                )
            )

    def add_openings(comp, xr, yr, depth, where, label):
        """Take out each requested wall of this rectangle bar its corners."""
        for spec in comp.get("openings", []):
            side = need(spec, "side", where)
            if side not in SIDES:
                raise ValueError(
                    f"{where}: opening side must be one of {', '.join(SIDES)}, "
                    f"got {side!r}"
                )
            # The wall runs along the axis the side does not name.
            run = (yr[1] - yr[0]) if side.startswith("W") else (xr[1] - xr[0])

            corner = spec.get("corner")
            if corner is None:
                corner = 0.2 * run  # leaves the middle 60%, as a notch does
            o_depth = spec.get("depth")
            if o_depth is None:
                o_depth = depth  # rim to floor, the way a card holder opens

            if not 0 <= corner < run / 2:
                raise ValueError(
                    f"{where}: opening corner {corner} must be in "
                    f"[0, {run / 2:.1f}) to leave a gap between the posts -- "
                    f"0 takes the whole {run:.1f} mm wall out"
                )
            if not 0 < o_depth <= depth:
                raise ValueError(
                    f"{where}: opening depth {o_depth} must be in (0, {depth}], "
                    f"no deeper than the compartment it opens"
                )

            cuts.append(opening_cut(side, xr, yr, H, corner, o_depth))
            opened.append(
                (
                    label,
                    side,
                    corner,
                    run - 2 * corner,
                    o_depth,
                    wall_is_outer(side, xr, yr, W, L),
                )
            )

    def carve(comps, axis, xr, yr, default_depth, where, level):
        """Split one rectangle into a row along `axis`.

        A compartment holding compartments of its own recurses with the axis
        flipped, so its children divide it crosswise -- that is what turns
        nesting into a grid. Material left standing between the cavities is
        the divider, so dividers never have to be built, only left behind.
        """
        lo, hi = yr if axis == "L" else xr
        span = (hi - lo) - (len(comps) - 1) * T
        if span <= 0:
            raise ValueError(
                f"{where}: {len(comps)} compartments and {len(comps) - 1} "
                f"divider(s) do not fit the {hi - lo:.1f} mm available along {axis}"
            )

        pos = lo
        for comp, size in zip(comps, resolve_sizes(where, comps, span)):
            cname = need(comp, "name", where)
            here = f"{where}.{cname}"
            if size <= 0:
                raise ValueError(f"{here}: size must be positive, got {size}")

            cxr = (pos, pos + size) if axis == "W" else xr
            cyr = (pos, pos + size) if axis == "L" else yr
            pos += size + T

            depth = comp.get("depth")
            if depth is None:
                depth = default_depth  # inherited from the enclosing compartment

            label = "  " * level + cname
            kids = comp.get("compartments")
            if kids:
                placed.append((cname, level, False, cxr, cyr, depth, None))
                # A container's walls are real walls, so they can be cut too.
                add_notches(comp, cxr, cyr, depth, here, label)
                add_openings(comp, cxr, cyr, depth, here, label)
                carve(
                    kids,
                    "W" if axis == "L" else "L",
                    cxr,
                    cyr,
                    depth,
                    here,
                    level + 1,
                )
                continue

            if not 0 < depth <= H - F:
                raise ValueError(
                    f"{here}: depth {depth} must be in (0, {H - F}] to leave a "
                    f"floor under it"
                )
            z0 = H - depth  # raised floor when the compartment is shallow
            cuts.append(box(cxr, cyr, (z0, H + over)))
            placed.append((cname, level, True, cxr, cyr, depth, z0))
            add_notches(comp, cxr, cyr, depth, here, label)
            add_openings(comp, cxr, cyr, depth, here, label)

    carve(comps, split, (T, W - T), (T, L - T), H - F, where, 0)
    return cuts, placed, notched, opened


print("=" * 66)
print(f"Resource Tray Generator -- {CFG['game']['name']}")
print("=" * 66)
print(f"Build   {T} mm walls and dividers, {F} mm floor")
print()

for name, spec in VARIANTS.items():
    at = f"{WHERE} trays.variants.{name}"
    W, L, H = need(spec, "size", at)
    split, comps = need(spec, "split", at), need(spec, "compartments", at)

    if split not in ("L", "W"):
        raise ValueError(f"{at}: split must be 'L' or 'W', got {split!r}")
    if not comps:
        raise ValueError(f"{at}: needs at least one compartment")
    if W - 2 * T <= 0 or L - 2 * T <= 0 or H - F <= 0:
        raise ValueError(
            f"{at}: outside {W} x {L} x {H} mm leaves nothing inside "
            f"{T} mm walls and a {F} mm floor"
        )

    cuts, placed, notched, opened = plan(comps, split, W, L, H, at)

    mesh = trimesh.boolean.difference([box((0, W), (0, L), (0, H))] + cuts)
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_tray_{name}.stl"
    mesh.export(path)

    print("-" * 66)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm")
    print(f"    cavity    {W - 2 * T:.1f} x {L - 2 * T:.1f} x {H - F:.1f} mm")
    leaves = sum(1 for p in placed if p[2])
    print(f"    layout    {leaves} compartments, top row along {split}")
    print("  Compartments")
    print(f"    {'name':<18}{'w x l':>16}{'depth':>8}{'floor z':>9}{'holds':>11}")
    for cname, level, leaf, cxr, cyr, depth, z0 in placed:
        cw, cl = cxr[1] - cxr[0], cyr[1] - cyr[0]
        label = "  " * level + cname
        footprint = f"{cw:.1f} x {cl:.1f}"
        if leaf:
            print(
                f"    {label:<18}{footprint:>16}{depth:>8.1f}{z0:>9.1f}"
                f"{cw * cl * depth / 1000:>8.1f} ml"
            )
        else:
            print(f"    {label:<18}{footprint:>16}{'(split)':>8}")
    if notched:
        print("  Notches")
        print(
            f"    {'compartment':<18}{'side':>6}{'width':>8}{'deep':>7}"
            f"{'radius':>8}   wall"
        )
        for label, side, width, n_depth, radius, outer in notched:
            print(
                f"    {label:<18}{side:>6}{width:>8.1f}{n_depth:>7.1f}{radius:>8.1f}"
                f"   {'outer, opens outside' if outer else 'divider, joins neighbour'}"
            )
    if opened:
        print("  Openings")
        print(
            f"    {'compartment':<18}{'side':>6}{'corner':>8}{'gap':>8}"
            f"{'deep':>7}   wall"
        )
        for label, side, corner, gap, o_depth, outer in opened:
            print(
                f"    {label:<18}{side:>6}{corner:>8.1f}{gap:>8.1f}{o_depth:>7.1f}"
                f"   {'outer, opens outside' if outer else 'divider, joins neighbour'}"
            )
    print("  Mesh checks")
    report_mesh(mesh)
    print(f"  -> {path}")
    print()
