"""
Where everything goes in the game box, and whether it all fits.

Not a generator: nothing here builds a part. It reads the `box` section of
games/<game_id>.json -- layers stacked up the box, sections dividing each
layer along it, and the objects lined up across each section -- and works
out from that where every part actually sits. check_box.py is the script
that prints the answer.

Positions are never written down. They fall out of the order things are
written in: a layer starts where the layers below it end, a section starts
where the sections before it end, and an object starts where the object
before it in the same section ends. So resizing a tray moves everything
after it, which is the arithmetic this exists to stop doing by hand.

That gives every object an exact box, and every check below is a statement
about those boxes -- they are inside the game box, none of them intersect,
and each one has something under it. Stated the other way round, as budgets
per section, the two spanning cases would each need a rule of their own and
both would only approximate: an object reaching into the next section holds
a band there, and the next section's own list starts from the wall, inside
it. Intersecting boxes says the same thing exactly, and says it once.

An object longer than its section, or taller than its layer, does reach
into the next one, and repeating its id there reserves its band -- a repeat
is the same object, not a second one, so it moves the entries after it
along without being counted twice.

Schema errors are raised as they are found, the way the generators raise
theirs; misfits are collected, because the useful answer to "does this box
pack" is the whole list and not the first line of it.
"""

import itertools

import shapely
import trimesh

from gameconfig import box, dims, need, object_sizes

EPS = 1e-6  # everything here is mm to one decimal; this is float noise only

BOX_KEYS = ("size", "clearance", "extras", "layers")
LAYER_KEYS = ("size", "sections")
SECTION_KEYS = ("size", "place")
ENTRY_KEYS = ("id", "turn")

KEYS = "abcdefghijklmnopqrstuvwxyz0123456789"  # legend letters for the maps


class Placement:
    """One object, once, wherever the layout first puts it."""

    def __init__(self, oid, size, turn, source, note):
        self.id = oid
        self.size = size  # effective W, L, H, already turned
        self.turn = turn
        self.source = source
        self.note = note
        self.occurrences = []  # every (layer, section, index, w, turn) listed
        self.w = self.l = self.h = (0.0, 0.0)

    @property
    def first(self):
        return self.occurrences[0]

    def footprint(self):
        return shapely.box(self.w[0], self.l[0], self.w[1], self.l[1])

    def __repr__(self):
        return f"<{self.id} W{self.w} L{self.l} H{self.h}>"


class Occurrence:
    def __init__(self, layer, section, index, w, turn):
        self.layer = layer
        self.section = section
        self.index = index
        self.w = w
        self.turn = turn

    @property
    def at(self):
        return f"layer {self.layer} section {self.section}, entry {self.index + 1}"


class Section:
    def __init__(self, key, stated, entries):
        self.key = key
        self.stated = stated
        self.entries = entries  # [(object id, (w0, w1))] in written order
        self.size = 0.0
        self.l = (0.0, 0.0)


class Layer:
    def __init__(self, key, stated, sections):
        self.key = key
        self.stated = stated
        self.sections = sections
        self.size = 0.0
        self.h = (0.0, 0.0)


class Report:
    def __init__(self, name, size, clearance, usable):
        self.name = name
        self.size = size
        self.clearance = clearance
        self.usable = usable
        self.layers = []
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


def entry_of(item, at):
    """One entry of a `place` list: an id, or an id and how it is laid."""
    if isinstance(item, str):
        return item, False
    if not isinstance(item, dict):
        raise SystemExit(
            f"{at}: a placement is an object id, or an object carrying that id "
            f"and how it is laid, got {item!r}"
        )
    closed(item, ENTRY_KEYS, at, "a placement")
    turn = item.get("turn", False)
    if not isinstance(turn, bool):
        raise SystemExit(
            f"{at}: turn lays an object across, swapping its W and its L, so it "
            f"is true or false, got {turn!r}"
        )
    return need(item, "id", at), turn


def overlap(a, b):
    """How far two (lo, hi) ranges run through each other."""
    return min(a[1], b[1]) - max(a[0], b[0])


def read(cfg, where):
    """The box section, parsed into layers, sections and placements.

    Everything is checked for shape here and nothing for fit: this comes
    back with each object's effective size and every place it was listed,
    and knows nothing yet about where any of it lands.
    """
    block = closed(need(cfg, "box", where), BOX_KEYS, f"{where} box", "a box")
    size = dims(need(block, "size", f"{where} box"), 3, f"{where} box", "size")
    clear = block.get("clearance") or 0.0
    if clear < 0:
        raise SystemExit(
            f"{where} box: clearance is slack taken off the box, so it cannot "
            f"be negative, got {clear}"
        )
    usable = [d - clear for d in size]
    if any(d <= 0 for d in usable):
        raise SystemExit(
            f"{where} box: a clearance of {clear} mm leaves nothing of a "
            f"{size[0]} x {size[1]} x {size[2]} mm box"
        )

    sizes = object_sizes(cfg, where)
    report = Report(cfg["game"]["name"], size, clear, usable)

    layers_block = need(block, "layers", f"{where} box")
    if not isinstance(layers_block, dict):
        raise SystemExit(
            f"{where} box.layers: must be an object keyed by layer name, got "
            f"{layers_block!r} -- layers stack in the order they are written, "
            f"bottom first"
        )

    for lkey, lspec in layers_block.items():
        lat = f"{where} box.layers.{lkey}"
        closed(lspec, LAYER_KEYS, lat, "a layer")
        sections_block = need(lspec, "sections", lat)
        if not isinstance(sections_block, dict):
            raise SystemExit(
                f"{lat}.sections: must be an object keyed by section name, got "
                f"{sections_block!r} -- sections divide the layer along L in "
                f"the order they are written"
            )

        sections = []
        for skey, sspec in sections_block.items():
            sat = f"{lat}.sections.{skey}"
            closed(sspec, SECTION_KEYS, sat, "a section")
            place = need(sspec, "place", sat)
            if not isinstance(place, list) or not place:
                raise SystemExit(
                    f"{sat}.place: must be a non-empty list of object ids, got "
                    f"{place!r} -- they line up across the section in the order "
                    f"they are written"
                )

            cursor, entries = 0.0, []
            for index, item in enumerate(place):
                eat = f"{sat}.place[{index}]"
                oid, turn = entry_of(item, eat)
                if oid not in sizes:
                    known = ", ".join(sorted(sizes)) or "(nothing is defined)"
                    raise SystemExit(
                        f"{eat}: nothing in this file is called {oid!r}\n"
                        f"objects here: {known}"
                    )
                w, ln, h = sizes[oid]["size"]
                eff = (ln, w, h) if turn else (w, ln, h)
                placed = report.placed.get(oid)
                if placed is None:
                    placed = Placement(
                        oid, eff, turn, sizes[oid]["where"], sizes[oid]["note"]
                    )
                    report.placed[oid] = placed
                span = (cursor, cursor + eff[0])
                placed.occurrences.append(Occurrence(lkey, skey, index, span, turn))
                entries.append((oid, span))
                cursor += eff[0]

            sections.append(Section(skey, scalar(sspec, "size", sat, "size"), entries))

        report.layers.append(Layer(lkey, scalar(lspec, "size", lat, "size"), sections))

    return report, sizes


def derive(report):
    """Turn written order into a position for every object.

    Three cumulative sums and one lookup back: a section is as long as its
    own contents unless it says otherwise, a layer as tall as its own, and
    an object sits where it was first listed. Contents means the objects
    whose *first* mention is there -- one reaching in from earlier already
    has its length counted where it started, and counting it again would
    push everything after it along twice.
    """
    firsts = {}  # (layer, section) -> ids first listed there
    for placed in report.placed.values():
        firsts.setdefault((placed.first.layer, placed.first.section), []).append(
            placed.id
        )

    ls = {}  # (layer, section) -> its range along L
    for layer in report.layers:
        cursor = 0.0
        for section in layer.sections:
            own = firsts.get((layer.key, section.key), [])
            fits = max([report.placed[oid].size[1] for oid in own], default=0.0)
            section.size = section.stated if section.stated is not None else fits
            section.l = (cursor, cursor + section.size)
            ls[(layer.key, section.key)] = section.l
            cursor += section.size

    lh = {}  # layer -> its range up H
    cursor = 0.0
    for layer in report.layers:
        own = [
            report.placed[oid]
            for section in layer.sections
            for oid in firsts.get((layer.key, section.key), [])
        ]
        fits = max([placed.size[2] for placed in own], default=0.0)
        layer.size = layer.stated if layer.stated is not None else fits
        layer.h = (cursor, cursor + layer.size)
        lh[layer.key] = layer.h
        cursor += layer.size

    for placed in report.placed.values():
        first = placed.first
        placed.w = first.w
        l0 = ls[(first.layer, first.section)][0]
        placed.l = (l0, l0 + placed.size[1])
        h0 = lh[first.layer][0]
        placed.h = (h0, h0 + placed.size[2])

    return ls, lh


def check_repeats(report, ls, lh):
    """Every mention of one object has to describe the same object."""
    for placed in report.placed.values():
        first = placed.first
        for occ in placed.occurrences[1:]:
            if abs(occ.w[0] - first.w[0]) > EPS:
                report.errors.append(
                    f"[{placed.id}] starts at W {first.w[0]:.1f} in "
                    f"{first.at}, but at W {occ.w[0]:.1f} in {occ.at} -- a "
                    f"repeat reserves the band the object already holds, so "
                    f"the entries before it have to come to the same width"
                )
            if occ.turn != first.turn:
                report.errors.append(
                    f"[{placed.id}] is turned in {occ.at} but not in "
                    f"{first.at} -- it is one object and can only lie one way"
                )
            reach_l = overlap(placed.l, ls[(occ.layer, occ.section)])
            reach_h = overlap(placed.h, lh[occ.layer])
            if reach_l <= EPS or reach_h <= EPS:
                report.errors.append(
                    f"[{placed.id}] is listed in {occ.at}, which it does not "
                    f"reach: it runs L {placed.l[0]:.1f} -> {placed.l[1]:.1f} "
                    f"and H {placed.h[0]:.1f} -> {placed.h[1]:.1f}, and that "
                    f"section is L {ls[(occ.layer, occ.section)][0]:.1f} -> "
                    f"{ls[(occ.layer, occ.section)][1]:.1f} in a layer "
                    f"H {lh[occ.layer][0]:.1f} -> {lh[occ.layer][1]:.1f}"
                )


def check_unlisted(report, ls, lh):
    """Reaching into a section without saying so leaves it unreserved."""
    for placed in report.placed.values():
        listed = {(occ.layer, occ.section) for occ in placed.occurrences}
        for layer in report.layers:
            if overlap(placed.h, lh[layer.key]) <= EPS:
                continue
            for section in layer.sections:
                key = (layer.key, section.key)
                if key in listed or overlap(placed.l, ls[key]) <= EPS:
                    continue
                report.warnings.append(
                    f"[{placed.id}] reaches into layer {layer.key} section "
                    f"{section.key} but is not listed there -- repeat its id "
                    f"in that section to reserve its W "
                    f"{placed.w[0]:.1f} -> {placed.w[1]:.1f} band"
                )


def check_bounds(report):
    """Nothing may stand outside the box, and no budget may overrun it."""
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

    total = sum(layer.size for layer in report.layers)
    if total > uh + EPS:
        report.errors.append(
            f"the layers come to {total:.1f} mm of H, past the {uh:.1f} mm the box has"
        )
    for layer in report.layers:
        along = sum(section.size for section in layer.sections)
        if along > ul + EPS:
            report.errors.append(
                f"layer {layer.key} divides into {along:.1f} mm of L, past "
                f"the {ul:.1f} mm the box has"
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
    ls, lh = derive(report)
    check_repeats(report, ls, lh)
    check_unlisted(report, ls, lh)
    check_bounds(report)
    check_overlaps(report)
    check_support(report)
    check_placed(report, sizes)
    return report


# --- saying what it found ------------------------------------------------


def plan_map(report, layer, keyed, cols=58, max_rows=18):
    """A top-down plan of one layer: W across the page, L down it.

    Rough on purpose -- it is there to show the shape of an arrangement at
    a glance, and the numbers above it are the ones to read. A cell two
    objects both claim is drawn as '!', so a collision shows up as a scar
    rather than as whichever object happened to be drawn second.
    """
    uw, ul = report.usable[0], report.usable[1]
    rows = max(1, min(max_rows, round(cols * (ul / uw) / 2)))
    grid = [[" "] * cols for _ in range(rows)]

    for placed, key in keyed:
        c0 = max(0, min(cols - 1, round(placed.w[0] / uw * cols)))
        c1 = max(c0 + 1, min(cols, round(placed.w[1] / uw * cols)))
        r0 = max(0, min(rows - 1, round(placed.l[0] / ul * rows)))
        r1 = max(r0 + 1, min(rows, round(placed.l[1] / ul * rows)))
        for row in range(r0, r1):
            for col in range(c0, c1):
                grid[row][col] = "!" if grid[row][col] not in " " else key

    edge = "    +" + "-" * cols + "+"
    out = [f"    {0:<{cols + 1}}{uw:.0f}", edge]
    out += ["    |" + "".join(row) + "|" for row in grid]
    out.append(edge)
    out.append(f"    L {layer.l_used:.0f} of {ul:.0f} mm used")
    return out


def show(report):
    """The whole report, in the shape the generators print theirs."""
    uw, ul, uh = report.usable
    print("=" * 66)
    print(f"Box Layout -- {report.name}")
    print("=" * 66)
    print()
    print("  Box")
    print(f"    inside    {report.size[0]} x {report.size[1]} x {report.size[2]} mm")
    if report.clearance:  # or usable is the same three numbers again
        print(f"    clearance {report.clearance} mm off each axis")
        print(f"    usable    {uw:.1f} x {ul:.1f} x {uh:.1f} mm")
    stacked = sum(layer.size for layer in report.layers)
    print(f"    layers    {len(report.layers)}, {stacked:.1f} of {uh:.1f} mm of H")
    print()

    for layer in report.layers:
        layer.l_used = sum(section.size for section in layer.sections)
        fit = "stated" if layer.stated is not None else "its tallest"
        print("-" * 66)
        print(f"[{layer.key}]   H {layer.h[0]:.1f} -> {layer.h[1]:.1f} mm   ({fit})")
        print(
            f"    sections  {layer.l_used:.1f} of {ul:.1f} mm of L, "
            f"{ul - layer.l_used:.1f} free"
        )
        print()

        keyed, letters = [], iter(KEYS)
        for section in layer.sections:
            fit = "stated" if section.stated is not None else "its longest"
            print(
                f"  ({section.key})   L {section.l[0]:.1f} -> "
                f"{section.l[1]:.1f} mm   ({fit})"
            )
            used = 0.0
            for oid, span in section.entries:
                placed = report.placed[oid]
                key = next(letters, "*")
                keyed.append((placed, key))
                again = "  (again)" if placed.first.section != section.key else ""
                turned = "  (turned)" if placed.turn else ""
                print(
                    f"    {key}  {oid:<26}"
                    f"{placed.size[0]:6.1f} x{placed.size[1]:6.1f} x{placed.size[2]:5.1f}"
                    f"   W {span[0]:6.1f} ->{span[1]:7.1f}{turned}{again}"
                )
                if placed.note:
                    print(f"       {' ' * 26}{placed.note}")
                used = max(used, span[1])
            if uw - used > EPS:
                print(
                    f"       {'free':<26}{uw - used:6.1f}"
                    f"{'':>15}   W {used:6.1f} ->{uw:7.1f}"
                )
            print()

        for line in plan_map(report, layer, keyed):
            print(line)
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
    so a layer can be told from the floor it is over.
    """

    def shrink(span):
        return (span[0] + 0.1, max(span[0] + 0.2, span[1] - 0.1))

    uw, ul, _ = report.usable
    parts = [box((0.0, uw), (0.0, ul), (-1.0, 0.0))]
    for placed in report.placed.values():
        parts.append(box(shrink(placed.w), shrink(placed.l), shrink(placed.h)))
    trimesh.util.concatenate(parts).export(path)
    return path
