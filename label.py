"""
Embossed labels, for either generator.

A tray compartment and a card well cavity are the same thing to a label:
a rectangle of floor at a known height, wanting words on it. So the sizing,
the fitting and the checks live here once, and each generator says where
the floor is and prints the result in its own house style.

A label either stands proud of the floor or is cut into it: state height
and it rises, state depth and it sinks. Neither overhangs -- one adds to a
floor that is already there, the other takes from it, and both leave the
part printable without supports.

A section may state its own defaults for everything but the words, the way
it does for separators, so a game can be labelled in one house style
without repeating the numbers on every compartment.

The glyphs come from stroke_font; see gameconfig for the emboss schema.
"""

import trimesh
from shapely import affinity

import stroke_font
from gameconfig import need

# Label defaults. A label that states nothing is sized to the compartment,
# so these only set the proportions it is sized to.
EMB_HEIGHT = 0.6  # how far the letters stand off the floor
EMB_STROKE = 0.14  # stroke width as a fraction of cap height
EMB_MIN_STROKE = 0.8  # ... but never finer, or the slicer drops it
EMB_MARGIN = 1.5  # floor left clear around the label
EMB_MAX_SIZE = 10.0  # a self-sized label stops growing here: it is a label,
# not a billboard, and a big compartment does not want 20 mm capitals. State
# size to go bigger.
EMB_SINK = 0.2  # letters buried in the floor, so the union overlaps
EMB_MIN_FLOOR = 0.4  # material left under a cut label, about two layers,
# so an engraved floor does not come out as a window
EMB_MIN_RATIO = 3.0  # cap height per stroke width, under which the counters
# close up and the label prints as a blob -- the default ratio is over 7

# What a label may be given beyond its text, and so what a section may
# default on its behalf.
EMB_KEYS = ("size", "stroke", "height", "depth", "along", "leading")


def emboss_defaults(section, where):
    """The emboss block a section states, for every label under it to start from.

    Closed to those four keys, and a typo in a block whose whole job is to
    be silently inherited would otherwise never be noticed. The text is not
    among them: it belongs to the label that carries it.
    """
    spec = section.get("emboss") or {}
    if not isinstance(spec, dict):
        raise ValueError(f"{where} emboss: must be an object, got {spec!r}")
    if "height" in spec and "depth" in spec:
        raise ValueError(
            f"{where} emboss: height raises a label and depth cuts it in, so a "
            f"section defaults one way or the other, not both"
        )
    unknown = [key for key in spec if key not in EMB_KEYS]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{where} emboss: cannot default {named} for a whole section -- it "
            f"takes {', '.join(EMB_KEYS)}, and text belongs to each label"
        )
    return spec


def emboss_solid(spec, xr, yr, z0, where, defaults=None):
    """A label standing proud of one floor, given the rect it has to fit.

    `xr` and `yr` bound that floor and `z0` is the height it sits at, which
    is all this needs to know -- a tray compartment and a card well cavity
    are the same problem seen twice.

    Sized to the rect and turned to run along whichever way is longer unless
    the label says otherwise, so labelling a part should not need a number
    typed per label to look right.

    Text may be one string, a string with newlines in it, or a list of
    lines; several lines are centred on each other and spaced by whatever
    the glyphs in them need, unless leading says otherwise.

    Anything the label does not state falls back to its section's defaults,
    and only then to the sizing here -- so a label may still say null to a
    defaulted size and have it worked out from the room it has.

    Returns the solid, and the label as it worked out. Whether that solid
    is added to the part or taken out of it comes back as `cut`, because a
    label that states depth is engraved rather than raised.
    """
    own = spec
    if "height" in own and "depth" in own:
        raise ValueError(
            f"{where}: a label either stands proud or is cut in, so state "
            f"height or depth, not both"
        )
    spec = {**(defaults or {}), **own}  # the label's own word wins
    # Saying which way it goes overrides an inherited default of the other
    # kind, rather than colliding with it.
    if "depth" in own:
        spec.pop("height", None)
    elif "height" in own:
        spec.pop("depth", None)

    said = need(spec, "text", where)
    lines = stroke_font.lines_of(said)
    if lines is None:
        raise ValueError(
            f"{where}: emboss text must be a string, or a list of strings for "
            f"several lines, got {said!r}"
        )
    lines = [line.strip() for line in lines]
    while lines and not lines[0]:  # a blank line top or bottom spaces nothing
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise ValueError(f"{where}: emboss text must be some text, got {said!r}")

    # Before anything reads the glyphs, since measuring the line spacing
    # walks them and would trip over one the font has never heard of.
    missing = stroke_font.unsupported(lines)
    if missing:
        raise ValueError(
            f"{where}: nothing to draw {', '.join(repr(c) for c in missing)} with "
            f"-- this font has {stroke_font.SUPPORTED!r}, and lower case is "
            f"raised as capitals"
        )

    leading = spec.get("leading")
    if leading is None:
        leading = stroke_font.line_gap(lines)  # measured from these very glyphs
    if leading < stroke_font.MIN_LEADING:
        raise ValueError(
            f"{where}: leading is baseline to baseline in cap heights, and under "
            f"{stroke_font.MIN_LEADING} one line's capitals run into the line "
            f"above whatever the glyphs are -- got {leading}"
        )

    w, span_l = xr[1] - xr[0], yr[1] - yr[0]
    along = spec.get("along")
    if along is None:
        along = "W" if w >= span_l else "L"  # the long way, which is where the room is
    if along not in ("W", "L"):
        raise ValueError(f"{where}: emboss along must be 'W' or 'L', got {along!r}")

    room_along = (w if along == "W" else span_l) - 2 * EMB_MARGIN
    room_across = (span_l if along == "W" else w) - 2 * EMB_MARGIN
    unit_w, unit_h = stroke_font.extents(lines, leading)  # per 1 mm of cap

    size, stroke = spec.get("size"), spec.get("stroke")
    if size is None:
        # The stroke widens the text as well as thickening it, and itself
        # follows the cap height, so settle the two together: guess a size
        # ignoring the stroke, then let each correct the other.
        size = min(room_along / unit_w, room_across / unit_h)
        for _ in range(3):
            trial = stroke
            if trial is None:
                trial = max(EMB_MIN_STROKE, EMB_STROKE * size)
            size = min((room_along - trial) / unit_w, (room_across - trial) / unit_h)
        size = min(size, EMB_MAX_SIZE)
    if stroke is None:
        stroke = max(EMB_MIN_STROKE, EMB_STROKE * size)

    cut = "depth" in spec  # depth is what asks for engraving, and sets it
    which = "depth" if cut else "height"
    amount = spec["depth"] if cut else spec.get("height", EMB_HEIGHT)

    if size <= 0:
        raise ValueError(
            f"{where}: no room to emboss {said!r} -- this floor leaves "
            f"{room_along:.1f} x {room_across:.1f} mm inside its {EMB_MARGIN} mm "
            f"margin, and {len(lines)} line(s) will not go in it"
        )
    if stroke <= 0 or amount is None or amount <= 0:
        raise ValueError(
            f"{where}: emboss stroke and {which} must be positive, got "
            f"{stroke} and {amount}"
        )
    if cut and amount > z0 - EMB_MIN_FLOOR:
        raise ValueError(
            f"{where}: cutting {amount} mm into {z0} mm of floor would leave "
            f"{z0 - amount:.2f} mm under the letters -- keep at least "
            f"{EMB_MIN_FLOOR} mm below a cut, or raise the label with height "
            f"instead of sinking it with depth"
        )
    if size < EMB_MIN_RATIO * stroke:
        raise ValueError(
            f"{where}: a {size:.1f} mm cap in a {stroke:.1f} mm stroke closes the "
            f"letters up into a blob -- this label needs a cap of at least "
            f"{EMB_MIN_RATIO * stroke:.1f} mm, so find it more floor, a finer "
            f"stroke, fewer lines, or leave it unlabelled"
        )

    geom = stroke_font.outline(lines, size, stroke, leading)
    x0, y0, x1, y1 = geom.bounds
    drawn_w, drawn_h = x1 - x0, y1 - y0
    if drawn_w > room_along + 1e-6 or drawn_h > room_across + 1e-6:
        raise ValueError(
            f"{where}: {said!r} at {size} mm cap comes to {drawn_w:.1f} x "
            f"{drawn_h:.1f} mm, more than the {room_along:.1f} x {room_across:.1f} "
            f"mm this floor leaves -- drop size, or leave it out and the label "
            f"sizes itself"
        )

    if along == "L":
        geom = affinity.rotate(geom, 90)
    geom = affinity.translate(geom, (xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2)

    # A raised label is buried a little, so the union is an overlap rather
    # than two solids touching exactly at the floor plane. A cut one runs
    # the other way and overshoots upward instead, to break the surface
    # cleanly on its way out.
    if cut:
        tall, base = amount + 2.0, z0 - amount
    else:
        sink = min(EMB_SINK, z0 / 2)
        tall, base = amount + sink, z0 - sink

    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    solid = trimesh.util.concatenate(
        [trimesh.creation.extrude_polygon(poly, tall) for poly in polys]
    )
    solid.apply_translation([0, 0, base])
    return solid, {
        "text": " / ".join(lines).upper(),
        "size": size,
        "stroke": stroke,
        "cut": cut,
        "amount": amount,
        "along": along,
        "w": drawn_w,
        "h": drawn_h,
    }
