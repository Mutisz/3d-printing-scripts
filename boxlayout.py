"""
Where everything goes in the game box, and whether it all fits.

Not a generator: nothing here builds a part. It reads the `box` section of
games/<game_id>.json -- the things in the box, and which way each run of
them goes -- and works out from that where every part actually sits.
check_box.py is the script that prints the answer.

The arrangement is one list. Its entries follow each other across W, and
any entry may itself be a run: `along` says which way that run goes, and
its own entries follow each other along it, from the corner the run was
handed, left- and floor-aligned across the other two. A run is as long as
its contents come to along its axis, and as wide and as tall as the widest
and tallest thing in it. Runs hold runs, so the box is described to
whatever depth the box actually has.

Positions are never written down. They fall out of the order things are
written in: an entry starts where the entry before it in the same run
ends. So resizing a tray moves everything after it, which is the
arithmetic this exists to stop doing by hand -- and it moves only what is
genuinely stacked on it, not everything at the same height elsewhere in
the box.

That gives every object an exact box, and every check below is a statement
about those boxes: they are inside the game box, none of them intersect,
and each one has something under it. Stated the other way round, as a
budget per shelf, each of those would need a rule of its own and each
would only approximate. Intersecting boxes says it exactly, and once.

An object is named once. Where it goes is the arrangement's business, and
the arrangement already says.

Because a position comes only from what was written before it, a thing
standing over an empty corner has nothing to push it clear of that corner.
An entry may therefore also be a gap: so much space, holding nothing.

Schema errors are raised as they are found, the way the generators raise
theirs; misfits are collected, because the useful answer to "does this box
pack" is the whole list and not the first line of it.
"""

import itertools

import shapely
import trimesh

from gameconfig import box, dims, need, object_sizes

EPS = 1e-6  # everything here is mm to one decimal; this is float noise only

BOX_KEYS = ("size", "clearance", "extras", "place")
ENTRY_KEYS = ("id", "turn")
GROUP_KEYS = ("along", "size", "place")
GAP_KEYS = ("gap",)

AXES = {"W": 0, "L": 1, "H": 2}

NAME = 26  # narrowest the report's name column is ever drawn


class Placement:
    """One object, where the arrangement puts it."""

    def __init__(self, oid, size, turn, source, note, path):
        self.id = oid
        self.size = size  # effective W, L, H, already turned
        self.turn = turn
        self.source = source
        self.note = note
        self.path = path  # where it was written, as a run of entry numbers
        self.w = self.l = self.h = (0.0, 0.0)

    def footprint(self):
        return shapely.box(self.w[0], self.l[0], self.w[1], self.l[1])

    def __repr__(self):
        return f"<{self.id} W{self.w} L{self.l} H{self.h}>"


class Leaf:
    """One entry naming an object, and how it lies."""

    def __init__(self, oid, turn, extent, path):
        self.oid = oid
        self.turn = turn
        self.extent = extent  # W, L, H, already turned
        self.path = path
        self.axis = "W"  # the axis its band is measured on, set by the walk
        self.band = (0.0, 0.0)


class Gap:
    """Space left deliberately empty, so what follows starts clear of it.

    Everything else takes its position from what is written before it, so
    a thing standing over an empty corner has nothing to push it past that
    corner -- and the only way to say "start 12 mm in" was to find some
    object 12 mm wide to put there first. This is that, without the
    object: it reserves its length along the run that holds it, and
    nothing at all across the other two.
    """

    def __init__(self, size, path, axis):
        self.size = size
        self.path = path
        self.axis = axis
        self.band = (0.0, 0.0)
        self.extent = tuple(
            size if i == AXES[axis] else 0.0 for i in range(3)
        )


class Group:
    """A run of entries along one axis, inside the band its parent gives it.

    It is as long as its contents come to along its own axis -- or as long
    as it says, where it says -- and as wide and as tall as the widest and
    tallest thing in it.
    """

    def __init__(self, along, stated, children, path):
        self.along = along
        self.stated = stated
        self.children = children
        self.path = path
        self.axis = "W"
        self.band = (0.0, 0.0)
        run = AXES[along]
        along_it = sum(child.extent[run] for child in children)
        self.extent = tuple(
            (stated if stated is not None else along_it)
            if axis == run
            else max(child.extent[axis] for child in children)
            for axis in range(3)
        )


class Report:
    def __init__(self, name, size, clearance, usable):
        self.name = name
        self.size = size
        self.clearance = clearance
        self.usable = usable
        self.entries = []  # the arrangement, as written
        self.placed = {}
        self.errors = []
        self.warnings = []


def closed(block, keys, at, what):
    """A block held to the keys it takes, so a typo cannot pass unread."""
    if not isinstance(block, dict):
        raise SystemExit(f"{at}: must be an object, got {block!r}")
    unknown = [key for key in block if key not in keys]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise SystemExit(
            f"{at}: {named} is not something {what} takes -- it takes {', '.join(keys)}"
        )
    return block


def scalar(block, key, at, what):
    """An optional positive number, or None where it is left to work out."""
    if block.get(key) is None:
        return None
    try:
        value = float(block[key])
    except (TypeError, ValueError):
        raise SystemExit(f"{at}: {what} must be a number in mm, got {block[key]!r}")
    if value <= 0:
        raise SystemExit(f"{at}: {what} must be positive, got {value}")
    return value


def place_of(block, at, path, sizes, seen, axis):
    """The `place` list of the box or of a run, as a list of nodes."""
    place = need(block, "place", at)
    if not isinstance(place, list) or not place:
        raise SystemExit(
            f"{at}.place: must be a non-empty list of object ids, got "
            f"{place!r} -- they follow each other in the order they are "
            f"written"
        )
    return [
        node_of(
            item,
            f"{at}.place[{index}]",
            f"{path}.{index + 1}" if path else str(index + 1),
            sizes,
            seen,
            axis,
        )
        for index, item in enumerate(place)
    ]


def node_of(item, at, path, sizes, seen, axis):
    """One entry: an object, how it is laid, or a run of entries of its own."""
    if isinstance(item, str):
        item = {"id": item}
    if not isinstance(item, dict):
        raise SystemExit(
            f"{at}: a placement is an object id, an object carrying that id "
            f"and how it is laid, or a run of placements along an axis of its "
            f"own, got {item!r}"
        )

    forms = [key for key in ("id", "along", "gap") if key in item]
    if len(forms) > 1:
        named = " and ".join(repr(key) for key in forms)
        raise SystemExit(
            f"{at}: an entry is one object, a run of them, or a gap left "
            f"empty -- this one carries {named} together"
        )

    if "gap" in item:
        closed(item, GAP_KEYS, at, "a gap")
        size = scalar(item, "gap", at, "a gap")
        if size is None:
            raise SystemExit(
                f"{at}: a gap is how much space to leave empty, in mm"
            )
        return Gap(size, path, axis)

    if "place" in item and "along" not in item:
        raise SystemExit(
            f"{at}: a run of placements has to say which way it goes -- add "
            f"'along': {' or '.join(repr(axis) for axis in AXES)}"
        )

    if "along" in item:
        closed(item, GROUP_KEYS, at, "a run of placements")
        along = item["along"]
        if along not in AXES:
            raise SystemExit(
                f"{at}: along says which way a run goes, so it is "
                f"{', '.join(AXES)}, got {along!r}"
            )
        children = place_of(item, at, path, sizes, seen, along)
        return Group(along, scalar(item, "size", at, "size"), children, path)

    closed(item, ENTRY_KEYS, at, "a placement")
    turn = item.get("turn", False)
    if not isinstance(turn, bool):
        raise SystemExit(
            f"{at}: turn lays an object across, swapping its W and its L, so it "
            f"is true or false, got {turn!r}"
        )
    oid = need(item, "id", at)
    if oid not in sizes:
        known = ", ".join(sorted(sizes)) or "(nothing is defined)"
        raise SystemExit(
            f"{at}: nothing in this file is called {oid!r}\nobjects here: {known}"
        )
    if oid in seen:
        raise SystemExit(
            f"{at}: {oid!r} is placed here and at {seen[oid]} -- one object "
            f"goes in one place, and the arrangement already says where. "
            f"Name it once"
        )
    seen[oid] = at
    w, ln, h = sizes[oid]["size"]
    return Leaf(oid, turn, (ln, w, h) if turn else (w, ln, h), path)


def overlap(a, b):
    """How far two (lo, hi) ranges run through each other."""
    return min(a[1], b[1]) - max(a[0], b[0])


def read(cfg, where):
    """The box section, parsed into the arrangement it describes.

    Everything is checked for shape here and nothing for fit: this comes
    back with each entry's effective size, and knows nothing yet about
    where any of it lands.
    """
    at = f"{where} box"
    block = closed(need(cfg, "box", where), BOX_KEYS, at, "a box")
    size = dims(need(block, "size", at), 3, at, "size")
    clear = block.get("clearance") or 0.0
    if clear < 0:
        raise SystemExit(
            f"{at}: clearance is slack taken off the box, so it cannot "
            f"be negative, got {clear}"
        )
    usable = [d - clear for d in size]
    if any(d <= 0 for d in usable):
        raise SystemExit(
            f"{at}: a clearance of {clear} mm leaves nothing of a "
            f"{size[0]} x {size[1]} x {size[2]} mm box"
        )

    sizes = object_sizes(cfg, where)
    report = Report(cfg["game"]["name"], size, clear, usable)
    report.entries = place_of(block, at, "", sizes, {}, "W")
    return report, sizes


def walk(report, sizes, node, origin, axis):
    """Hand a node the corner it starts from, and everything it holds theirs."""
    node.axis = axis
    start = origin[AXES[axis]]
    node.band = (start, start + node.extent[AXES[axis]])

    if isinstance(node, Gap):
        return

    if isinstance(node, Group):
        run = AXES[node.along]
        cursor = origin[run]
        for child in node.children:
            corner = list(origin)
            corner[run] = cursor
            walk(report, sizes, child, tuple(corner), node.along)
            cursor += child.extent[run]
        return

    placed = Placement(
        node.oid,
        node.extent,
        node.turn,
        sizes[node.oid]["where"],
        sizes[node.oid]["note"],
        node.path,
    )
    placed.w = (origin[0], origin[0] + node.extent[0])
    placed.l = (origin[1], origin[1] + node.extent[1])
    placed.h = (origin[2], origin[2] + node.extent[2])
    report.placed[node.oid] = placed


def derive(report, sizes):
    """Turn written order into a position for every object.

    One walk down from the corner of the box. The top-level entries follow
    each other across W, and each hands the corners on to whatever it
    holds; a run's contents start from the run's own corner and follow
    each other along its axis. Nothing needs measuring first, because a
    node already knows how big it is.
    """
    cursor = 0.0
    for node in report.entries:
        walk(report, sizes, node, (cursor, 0.0, 0.0), "W")
        cursor += node.extent[0]


def check_bounds(report):
    """Nothing may stand outside the box."""
    uw, ul, uh = report.usable
    for placed in report.placed.values():
        for axis, span, limit in (
            ("W", placed.w, uw),
            ("L", placed.l, ul),
            ("H", placed.h, uh),
        ):
            if span[1] > limit + EPS:
                report.errors.append(
                    f"[{placed.id}] ends at {axis} {span[1]:.1f}, past the "
                    f"{limit:.1f} mm of {axis} the box has"
                )


def check_overlaps(report):
    """Two things cannot be in the same place."""
    for a, b in itertools.combinations(report.placed.values(), 2):
        through = [
            (axis, overlap(getattr(a, attr), getattr(b, attr)))
            for axis, attr in (("W", "w"), ("L", "l"), ("H", "h"))
        ]
        if all(mm > EPS for _, mm in through):
            by = ", ".join(f"{mm:.1f} mm in {axis}" for axis, mm in through)
            report.errors.append(f"[{a.id}] overlaps [{b.id}] by {by}")


def check_support(report):
    """Everything off the floor needs something under it to rest on."""
    for placed in report.placed.values():
        if placed.h[0] <= EPS:
            continue
        beneath = [
            other
            for other in report.placed.values()
            if other is not placed
            and other.h[1] <= placed.h[0] + EPS
            and overlap(other.w, placed.w) > EPS
            and overlap(other.l, placed.l) > EPS
        ]
        if not beneath:
            report.errors.append(
                f"[{placed.id}] has nothing under it: it starts at "
                f"H {placed.h[0]:.1f} over W {placed.w[0]:.1f} -> "
                f"{placed.w[1]:.1f}, L {placed.l[0]:.1f} -> {placed.l[1]:.1f}, "
                f"and nothing below reaches that far up or that far across"
            )
            continue

        touching = [other for other in beneath if abs(other.h[1] - placed.h[0]) <= EPS]
        if not touching:
            top = max(other.h[1] for other in beneath)
            report.warnings.append(
                f"[{placed.id}] sits at H {placed.h[0]:.1f} but the highest "
                f"thing under it tops out at {top:.1f} -- a "
                f"{placed.h[0] - top:.1f} mm drop, so it rests on air"
            )
            continue

        bare = placed.footprint().difference(
            shapely.union_all([other.footprint() for other in touching])
        )
        if bare.area > EPS:
            names = ", ".join(sorted(other.id for other in touching))
            report.warnings.append(
                f"[{placed.id}] rests on {names}, leaving {bare.area:.0f} mm2 "
                f"of its {placed.size[0] * placed.size[1]:.0f} mm2 footprint "
                f"unsupported"
            )


def check_placed(report, sizes):
    """A part built and then left out of the box is the likeliest slip."""
    missing = sorted(oid for oid in sizes if oid not in report.placed)
    if missing:
        listed = "\n".join(f"{oid:<28}{sizes[oid]['where']}" for oid in missing)
        report.warnings.append(
            f"{len(missing)} of {len(sizes)} objects are placed nowhere:\n{listed}"
        )


def check(cfg, where):
    """Read the box section, place everything in it, and check the lot."""
    report, sizes = read(cfg, where)
    derive(report, sizes)
    check_bounds(report)
    check_overlaps(report)
    check_support(report)
    check_placed(report, sizes)
    return report


# --- saying what it found ------------------------------------------------


def label_of(node):
    """What a node is called in the report: its id, or the space it is."""
    if isinstance(node, Group):
        return f"along {node.along}" + ("  (stated)" if node.stated else "")
    if isinstance(node, Gap):
        return "gap"
    return node.oid


def name_width(entries):
    """How wide the name column has to be for the whole box to line up.

    Indenting a run's contents eats into the column rather than shifting
    the numbers right, which keeps every size and every range under one
    another -- until a name is longer than what indenting has left it. So
    the arrangement is measured first and the column opened up to fit its
    worst line, and the sizes still start in one place.
    """

    def deep(node, depth):
        yield 2 * depth + len(label_of(node))
        for child in getattr(node, "children", ()):
            yield from deep(child, depth + 1)

    return max([wide for node in entries for wide in deep(node, 0)] + [NAME])


def entry_lines(report, node, depth, width):
    """One line per entry, indented under the run that holds it.

    Each line reads on the axis of the run it belongs to, not always on W:
    the box's own entries follow each other across W, and the entries of a
    run follow each other along whatever axis the run named.
    """
    pad = "  " * depth
    field = width - 2 * depth
    lo, hi = node.band
    size = f"{node.extent[0]:6.1f} x{node.extent[1]:6.1f} x{node.extent[2]:5.1f}"
    where = f"   {node.axis} {lo:6.1f} ->{hi:7.1f}"

    if isinstance(node, Group):
        yield f"    {pad}{label_of(node):<{field}}{size}{where}"
        for child in node.children:
            yield from entry_lines(report, child, depth + 1, width)
        return

    if isinstance(node, Gap):
        yield f"    {pad}{label_of(node):<{field}}{size}{where}"
        return

    placed = report.placed[node.oid]
    turned = "  (turned)" if node.turn else ""
    yield f"    {pad}{label_of(node):<{field}}{size}{where}{turned}"
    if placed.note:
        yield f"    {pad}{' ' * field}{placed.note}"


def show(report):
    """The whole report, in the shape the generators print theirs."""
    uw, ul, uh = report.usable
    across = sum(node.extent[0] for node in report.entries)
    along = max([node.extent[1] for node in report.entries], default=0.0)
    up = max([node.extent[2] for node in report.entries], default=0.0)

    print("=" * 66)
    print(f"Box Layout -- {report.name}")
    print("=" * 66)
    print()
    print("  Box")
    print(f"    inside    {report.size[0]} x {report.size[1]} x {report.size[2]} mm")
    if report.clearance:  # or usable is the same three numbers again
        print(f"    clearance {report.clearance} mm off each axis")
        print(f"    usable    {uw:.1f} x {ul:.1f} x {uh:.1f} mm")
    print(f"    filled    {across:.1f} x {along:.1f} x {up:.1f} mm")
    print()
    print("-" * 66)
    print()

    width = name_width(report.entries)
    for node in report.entries:
        for line in entry_lines(report, node, 0, width):
            print(line)
    if uw - across > EPS:
        print(
            f"    {'free':<{width}}{uw - across:6.1f}"
            f"{'':>15}   W {across:6.1f} ->{uw:7.1f}"
        )
    print()

    print("-" * 66)
    for kind, said in [("warn", w) for w in report.warnings] + [
        ("ERROR", e) for e in report.errors
    ]:
        head, *rest = said.split("\n")
        print(f"  {kind:<6} {head}")
        for line in rest:  # a list that would run off the page as one line
            print(f"           {line}")
    if not report.warnings and not report.errors:
        print("  Everything fits, everything is supported, nothing is left over.")
    print()


def preview(report, path):
    """One plain block per object, where the report says it sits.

    Shrunk a hair each way so neighbours that touch stay two blocks in the
    viewer rather than one, and stood on a thin plate the size of the box
    so the arrangement can be told from the floor it is over.
    """

    def shrink(span):
        return (span[0] + 0.1, max(span[0] + 0.2, span[1] - 0.1))

    uw, ul, _ = report.usable
    parts = [box((0.0, uw), (0.0, ul), (-1.0, 0.0))]
    for placed in report.placed.values():
        parts.append(box(shrink(placed.w), shrink(placed.l), shrink(placed.h)))
    trimesh.util.concatenate(parts).export(path)
    return path
