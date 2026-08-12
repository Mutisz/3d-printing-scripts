"""
Embossed labels, for either generator.

A tray compartment and a card holder cavity are the same thing to a label:
a rectangle of floor at a known height, wanting words on it. So the sizing,
the fitting and the checks live here once, and each generator says where
the floor is and prints the result in its own house style.

Nothing here overhangs -- the letters are raised from a floor that is
already there -- so a labelled part still prints without supports.

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
EMB_MIN_RATIO = 3.0  # cap height per stroke width, under which the counters
# close up and the label prints as a blob -- the default ratio is over 7


def emboss_solid(spec, xr, yr, z0, where):
    """A label standing proud of one floor, given the rect it has to fit.

    `xr` and `yr` bound that floor and `z0` is the height it sits at, which
    is all this needs to know -- a tray compartment and a card holder cavity
    are the same problem seen twice.

    Sized to the rect and turned to run along whichever way is longer unless
    the label says otherwise, so labelling a part should not need a number
    typed per label to look right.

    Returns the solid to add to the part, and what the report wants to say
    about it.
    """
    text = need(spec, "text", where)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{where}: emboss text must be some text, got {text!r}")
    text = text.strip()

    missing = stroke_font.unsupported(text)
    if missing:
        raise ValueError(
            f"{where}: nothing to draw {', '.join(repr(c) for c in missing)} with "
            f"-- this font has {stroke_font.SUPPORTED!r}, and lower case is "
            f"raised as capitals"
        )

    w, span_l = xr[1] - xr[0], yr[1] - yr[0]
    along = spec.get("along")
    if along is None:
        along = "W" if w >= span_l else "L"  # the long way, which is where the room is
    if along not in ("W", "L"):
        raise ValueError(f"{where}: emboss along must be 'W' or 'L', got {along!r}")

    room_along = (w if along == "W" else span_l) - 2 * EMB_MARGIN
    room_across = (span_l if along == "W" else w) - 2 * EMB_MARGIN
    unit_w, unit_h = stroke_font.extents(text)  # per 1 mm of cap height

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
    height = spec.get("height", EMB_HEIGHT)

    if size <= 0:
        raise ValueError(
            f"{where}: no room to emboss {text!r} -- this floor leaves "
            f"{room_along:.1f} x {room_across:.1f} mm inside its {EMB_MARGIN} mm "
            f"margin, and {len(text)} characters will not go in it"
        )
    if stroke <= 0 or height <= 0:
        raise ValueError(
            f"{where}: emboss stroke and height must be positive, got "
            f"{stroke} and {height}"
        )
    if size < EMB_MIN_RATIO * stroke:
        raise ValueError(
            f"{where}: a {size:.1f} mm cap in a {stroke:.1f} mm stroke closes the "
            f"letters up into a blob -- {text!r} needs a cap of at least "
            f"{EMB_MIN_RATIO * stroke:.1f} mm, so find it more floor, a finer "
            f"stroke, or leave it unlabelled"
        )

    geom = stroke_font.outline(text, size, stroke)
    x0, y0, x1, y1 = geom.bounds
    drawn_w, drawn_h = x1 - x0, y1 - y0
    if drawn_w > room_along + 1e-6 or drawn_h > room_across + 1e-6:
        raise ValueError(
            f"{where}: {text!r} at {size} mm cap comes to {drawn_w:.1f} x "
            f"{drawn_h:.1f} mm, more than the {room_along:.1f} x {room_across:.1f} "
            f"mm this floor leaves -- drop size, or leave it out and the label "
            f"sizes itself"
        )

    if along == "L":
        geom = affinity.rotate(geom, 90)
    geom = affinity.translate(geom, (xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2)

    # Bury the letters a little, so the union is an overlap rather than two
    # solids touching exactly at the floor plane.
    sink = min(EMB_SINK, z0 / 2)
    parts = [
        trimesh.creation.extrude_polygon(poly, height + sink)
        for poly in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom])
    ]
    solid = trimesh.util.concatenate(parts)
    solid.apply_translation([0, 0, z0 - sink])
    return solid, (text.upper(), size, stroke, height, along, drawn_w, drawn_h)
