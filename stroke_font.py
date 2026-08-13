"""
A single-stroke font, for labelling parts that have to come off a printer.

No font file and no font library: every glyph is a handful of polylines on
a 4 x 7 grid, thickened to whatever stroke width is asked for. That suits a
printer better than an outline font would -- every line ends up exactly one
stroke wide, so a label small enough to fit a compartment floor is still a
couple of clean extrusions rather than a hairline the slicer throws away.

Upper case only, and text is upper-cased on the way in: a tray label wants
capitals, and one set of glyphs is one set to keep legible. Polish letters
are carried too, built from the same bases with a mark added, so a label
reads the way the game box spells it.

Text may be several lines, given as a list or as one string with newlines
in it. Lines are centred on each other and spaced by whatever it takes to
keep them clear: plain capitals sit tight, and a line carrying an accent or
an ogonek is measured and given the room it needs.

outline() hands back shapely geometry in mm, centred on the origin, for the
caller to extrude however it likes.
"""

from shapely.geometry import LineString
from shapely.ops import unary_union

CELL_H = 7.0  # cap height, in grid units
MIN_LEADING = 1.2  # baselines closer than this, in cap heights, and one
# line's caps run into the line above it whatever the glyphs are
ADVANCE = 5.6  # pen step from one glyph to the next: 4 wide, the rest
# side bearing -- enough that a fat stroke does not weld neighbours together

# Each glyph is a tuple of polylines. Drawn with the pen down, in grid units,
# x rightward from 0 and y up from the baseline.
GLYPHS = {
    " ": (),
    "A": (((0, 0), (2, 7), (4, 0)), ((0.8, 2.8), (3.2, 2.8))),
    "B": (
        ((0, 0), (0, 7), (2.8, 7), (4, 5.9), (4, 4.6), (2.8, 3.5), (0, 3.5)),
        ((2.8, 3.5), (4, 2.4), (4, 1.1), (2.8, 0), (0, 0)),
    ),
    "C": (
        (
            (4, 5.6), (2.8, 7), (1.2, 7), (0, 5.6),
            (0, 1.4), (1.2, 0), (2.8, 0), (4, 1.4),
        ),
    ),
    "D": (((0, 0), (0, 7), (2.6, 7), (4, 5.6), (4, 1.4), (2.6, 0), (0, 0)),),
    "E": (((4, 7), (0, 7), (0, 0), (4, 0)), ((0, 3.5), (3, 3.5))),
    "F": (((4, 7), (0, 7), (0, 0)), ((0, 3.5), (3, 3.5))),
    "G": (
        (
            (4, 5.6), (2.8, 7), (1.2, 7), (0, 5.6), (0, 1.4), (1.2, 0),
            (2.8, 0), (4, 1.4), (4, 3.2), (2.2, 3.2),
        ),
    ),
    "H": (((0, 7), (0, 0)), ((4, 7), (4, 0)), ((0, 3.5), (4, 3.5))),
    "I": (((0.6, 7), (3.4, 7)), ((2, 7), (2, 0)), ((0.6, 0), (3.4, 0))),
    "J": (((4, 7), (4, 1.4), (2.8, 0), (1.2, 0), (0, 1.4), (0, 2.2)),),
    "K": (((0, 7), (0, 0)), ((4, 7), (0.2, 3.3)), ((1.5, 4.6), (4, 0))),
    "L": (((0, 7), (0, 0), (4, 0)),),
    "M": (((0, 0), (0, 7), (2, 3.6), (4, 7), (4, 0)),),
    "N": (((0, 0), (0, 7), (4, 0), (4, 7)),),
    "O": (
        (
            (1.2, 7), (2.8, 7), (4, 5.6), (4, 1.4), (2.8, 0),
            (1.2, 0), (0, 1.4), (0, 5.6), (1.2, 7),
        ),
    ),
    "P": (((0, 0), (0, 7), (2.8, 7), (4, 5.9), (4, 4.6), (2.8, 3.5), (0, 3.5)),),
    "Q": (
        (
            (1.2, 7), (2.8, 7), (4, 5.6), (4, 1.4), (2.8, 0),
            (1.2, 0), (0, 1.4), (0, 5.6), (1.2, 7),
        ),
        ((2.4, 1.6), (4.2, -0.3)),
    ),
    "R": (
        ((0, 0), (0, 7), (2.8, 7), (4, 5.9), (4, 4.6), (2.8, 3.5), (0, 3.5)),
        ((2.2, 3.5), (4, 0)),
    ),
    "S": (
        (
            (4, 5.9), (2.8, 7), (1.2, 7), (0, 5.9), (0, 4.7), (1.2, 3.5),
            (2.8, 3.5), (4, 2.3), (4, 1.1), (2.8, 0), (1.2, 0), (0, 1.1),
        ),
    ),
    "T": (((0, 7), (4, 7)), ((2, 7), (2, 0))),
    "U": (((0, 7), (0, 1.4), (1.2, 0), (2.8, 0), (4, 1.4), (4, 7)),),
    "V": (((0, 7), (2, 0), (4, 7)),),
    "W": (((0, 7), (1, 0), (2, 3.6), (3, 0), (4, 7)),),
    "X": (((0, 7), (4, 0)), ((0, 0), (4, 7))),
    "Y": (((0, 7), (2, 3.6), (4, 7)), ((2, 3.6), (2, 0))),
    "Z": (((0, 7), (4, 7), (0, 0), (4, 0)),),
    "0": (
        (
            (1.2, 7), (2.8, 7), (4, 5.6), (4, 1.4), (2.8, 0),
            (1.2, 0), (0, 1.4), (0, 5.6), (1.2, 7),
        ),
        ((0.7, 1.6), (3.3, 5.4)),
    ),
    "1": (((0.6, 5.4), (2, 7), (2, 0)), ((0.6, 0), (3.4, 0))),
    "2": (((0, 5.6), (1.2, 7), (2.8, 7), (4, 5.6), (4, 4.4), (0, 0), (4, 0)),),
    "3": (
        (
            (0, 7), (4, 7), (1.8, 3.8), (2.9, 3.8), (4, 2.6),
            (4, 1.2), (2.8, 0), (1.2, 0), (0, 1.2),
        ),
    ),
    "4": (((3, 0), (3, 7), (0, 2.4), (4, 2.4)),),
    "5": (
        (
            (4, 7), (0, 7), (0, 4.1), (2.8, 4.1), (4, 2.9),
            (4, 1.2), (2.8, 0), (1.2, 0), (0, 1.1),
        ),
    ),
    "6": (
        (
            (3.6, 6.2), (2.6, 7), (1.2, 7), (0, 5.6), (0, 1.4), (1.2, 0), (2.8, 0),
            (4, 1.2), (4, 2.5), (2.8, 3.7), (1.2, 3.7), (0, 2.5),
        ),
    ),
    "7": (((0, 7), (4, 7), (1.4, 0)),),
    "8": (
        (
            (1.2, 3.5), (0, 4.7), (0, 5.9), (1.2, 7), (2.8, 7), (4, 5.9),
            (4, 4.7), (2.8, 3.5), (1.2, 3.5), (0, 2.3), (0, 1.1), (1.2, 0),
            (2.8, 0), (4, 1.1), (4, 2.3), (2.8, 3.5),
        ),
    ),
    "9": (
        (
            (0.4, 0.8), (1.4, 0), (2.8, 0), (4, 1.4), (4, 5.6), (2.8, 7),
            (1.2, 7), (0, 5.8), (0, 4.5), (1.2, 3.3), (2.8, 3.3), (4, 4.5),
        ),
    ),
    "-": (((0.6, 3.5), (3.4, 3.5)),),
    "_": (((0, -0.6), (4, -0.6)),),
    "+": (((2, 1.6), (2, 5.4)), ((0.2, 3.5), (3.8, 3.5))),
    "=": (((0.2, 2.4), (3.8, 2.4)), ((0.2, 4.6), (3.8, 4.6))),
    "/": (((0, 0), (4, 7)),),
    ".": (((1.9, 0), (2.1, 0)),),
    ",": (((2.1, 0.3), (1.5, -0.9)),),
    ":": (((2, 1.4), (2, 1.6)), ((2, 4.9), (2, 5.1))),
    "'": (((2, 5.6), (2, 7)),),
    "!": (((2, 7), (2, 2)), ((2, 0), (2, 0.2))),
    "?": (((0, 5.6), (1.2, 7), (2.8, 7), (4, 5.6), (4, 4.8), (2, 3.2), (2, 2.2)),
          ((2, 0), (2, 0.2))),
    "(": (((3, 7), (1.4, 4.6), (1.4, 2.4), (3, 0)),),
    ")": (((1, 7), (2.6, 4.6), (2.6, 2.4), (1, 0)),),
}

# Polish letters: a base glyph plus its mark, rather than nine glyphs drawn
# again from scratch -- a fix to the base carries into all of them. Marks
# sit clear above the cap or below the baseline, so an accented word is
# taller than its cap height, which extents() reports and the caller sizes
# against.
ACUTE = ((1.5, 8.3), (3.0, 9.5))
DOT_ABOVE = ((2.0, 8.7), (2.2, 8.7))  # a stub, rounded into a dot by the cap
OGONEK_A = ((4, 0), (3.95, -0.85), (3.05, -1.45))  # hooks off the right
# leg, curling back under the letter: anything past x=4 would foul the
# next glyph, and PIENIĄDZE is exactly the word that catches it
OGONEK_E = ((3.2, 0), (3.5, -0.9), (2.6, -1.5))  # ... and off the bottom bar
BAR_L = ((-0.6, 3.5), (1.9, 4.7))  # crosses the stem, so it starts left of it

GLYPHS.update(
    {
        "Ą": GLYPHS["A"] + (OGONEK_A,),
        "Ć": GLYPHS["C"] + (ACUTE,),
        "Ę": GLYPHS["E"] + (OGONEK_E,),
        "Ł": GLYPHS["L"] + (BAR_L,),
        "Ń": GLYPHS["N"] + (ACUTE,),
        "Ó": GLYPHS["O"] + (ACUTE,),
        "Ś": GLYPHS["S"] + (ACUTE,),
        "Ź": GLYPHS["Z"] + (ACUTE,),
        "Ż": GLYPHS["Z"] + (DOT_ABOVE,),
    }
)

SUPPORTED = "".join(sorted(GLYPHS))


def lines_of(text):
    """The lines of a label: a list as given, or a string cut on newlines.

    None when it is neither, which is the caller's to report -- it knows
    which key in which file said it.
    """
    if isinstance(text, str):
        return text.split("\n")
    if isinstance(text, (list, tuple)) and all(isinstance(x, str) for x in text):
        return list(text)
    return None


def unsupported(lines):
    """The characters these lines have no glyph for, in order, once each."""
    seen, out = set(), []
    for line in lines:
        for ch in line.upper():
            if ch not in GLYPHS and ch not in seen:
                seen.add(ch)
                out.append(ch)
    return out


def line_gap(lines):
    """Baseline-to-baseline spacing, in cap heights, that keeps lines clear.

    Measured from the glyphs actually used rather than assumed, so a block
    of plain capitals stays tight and one carrying ACCENTS or an ogonek is
    opened up by exactly what those need.
    """
    tops, bottoms = [CELL_H], [0.0]  # the cap box, at the least
    for line in lines:
        for ch in line.upper():
            for poly in GLYPHS[ch]:
                for _, y in poly:
                    tops.append(y)
                    bottoms.append(y)
    room = max(tops) - min(bottoms) + 1.6  # 1.6 units of daylight between
    return max(MIN_LEADING, room / CELL_H)


def extents(lines, leading):
    """Width and height of the block per 1 mm of cap height, before any stroke.

    Enough to size the text against the room available without drawing it,
    which is what letting a label fit itself needs.
    """
    strokes = _block(lines, leading, 1.0 / CELL_H)
    if not strokes:
        return 0.0, 0.0
    xs = [p for poly in strokes for p, _ in poly]
    ys = [q for poly in strokes for _, q in poly]
    return max(xs) - min(xs), max(ys) - min(ys)


def _line_strokes(line):
    """Every polyline in one line, in grid units, pen starting at x = 0."""
    out, pen = [], 0.0
    for ch in line.upper():
        for poly in GLYPHS[ch]:
            out.append(tuple((pen + x, y) for x, y in poly))
        pen += ADVANCE
    return out


def _block(lines, leading, scale):
    """Every polyline in the block, lines centred on each other and scaled.

    A blank line draws nothing but still takes its turn, so it spaces the
    lines around it the way an empty line is meant to.
    """
    out = []
    for row, line in enumerate(lines):
        strokes = _line_strokes(line)
        xs = [x for poly in strokes for x, _ in poly]
        dx = -(min(xs) + max(xs)) / 2 if xs else 0.0
        dy = -row * leading * CELL_H
        out.extend(
            tuple(((x + dx) * scale, (y + dy) * scale) for x, y in poly)
            for poly in strokes
        )
    return out


def outline(lines, size, stroke, leading):
    """Shapely geometry for these lines, `size` mm from baseline to cap.

    Every polyline is thickened to `stroke` mm with round ends, so strokes
    meet cleanly at a corner and no join comes to a point that a nozzle
    could not lay down. The result is centred on the origin.
    """
    strokes = _block(lines, leading, size / CELL_H)
    if not strokes:
        return None
    geom = unary_union(
        [
            LineString(poly).buffer(stroke / 2, cap_style=1, join_style=1)
            for poly in strokes
        ]
    )
    x0, y0, x1, y1 = geom.bounds
    from shapely.affinity import translate

    return translate(geom, -(x0 + x1) / 2, -(y0 + y1) / 2)
