"""
Resource trays: open-top boxes divided into a row of compartments.

Each tray is a solid blank with one cavity milled per compartment, so the
outside dimensions come out exactly as asked -- they are the hard constraint
when a tray has to drop into a game box insert. Compartments sit in a single
row running along either the L or the W axis, separated by dividers as thick
as the walls.

Give a compartment an absolute size along the split axis, or None to let it
share out whatever the fixed ones leave over. A compartment may also be
shallower than the tray, which raises its floor and makes small pieces
easier to pinch out.
"""

import os

import trimesh

# ---- Parameters -------------------------------------------------------
T = 1.0  # wall and divider thickness
F = 1.0  # floor thickness

GAME_ID = "cafe_baras"
# name -> variant spec.
#   size          (W, L, H) outside dimensions, W across and L along
#   split         axis the row of compartments runs along: "L" or "W"
#   compartments  the row, in order, each one:
#                   name   label, used for the report
#                   size   extent along the split axis, or None to share
#                          out what the fixed ones leave over
#                   depth  optional, defaults to the full inside depth;
#                          less than that raises this compartment's floor
VARIANTS = {
    "coins": {
        "size": (70.0, 94.0, 21.0),
        "split": "L",
        "compartments": [
            {"name": "1", "size": None},
            {"name": "5", "size": 30},
        ],
    },
    # "tokens": {
    #     "size": (80.0, 60.0, 18.0),
    #     "split": "W",
    #     "compartments": [
    #         {"name": "markers", "size": 30.0},
    #         {"name": "tiles", "size": None, "depth": 10.0},
    #     ],
    # },
}

OUTDIR = f"./models/{GAME_ID}"
# -----------------------------------------------------------------------


def box(xr, yr, zr):
    ext = [xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0]]
    ctr = [(xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2]
    return trimesh.creation.box(
        extents=ext, transform=trimesh.transformations.translation_matrix(ctr)
    )


def resolve_sizes(name, comps, span):
    """Absolute size per compartment, sharing `span` out among the Nones."""
    autos = [c for c in comps if c.get("size") is None]
    fixed = sum(c["size"] for c in comps if c.get("size") is not None)

    if not autos:
        if abs(fixed - span) > 1e-6:
            raise ValueError(
                f"[{name}] compartments total {fixed:.1f} mm but {span:.1f} mm "
                f"is available -- adjust a size, change the outside dimension, "
                f"or set one size to None to absorb the difference"
            )
        return [c["size"] for c in comps]

    leftover = span - fixed
    if leftover <= 0:
        raise ValueError(
            f"[{name}] fixed compartments already total {fixed:.1f} mm of the "
            f"{span:.1f} mm available, leaving nothing for the {len(autos)} "
            f"sized None"
        )
    share = leftover / len(autos)
    return [share if c.get("size") is None else c["size"] for c in comps]


os.makedirs(OUTDIR, exist_ok=True)

print("=" * 66)
print("Resource Tray Generator")
print("=" * 66)
print(f"Build   {T} mm walls and dividers, {F} mm floor")
print()

for name, spec in VARIANTS.items():
    W, L, H = spec["size"]
    split, comps = spec["split"], spec["compartments"]

    if split not in ("L", "W"):
        raise ValueError(f"[{name}] split must be 'L' or 'W', got {split!r}")
    if not comps:
        raise ValueError(f"[{name}] needs at least one compartment")

    # The split axis loses two walls and a divider between each neighbour;
    # the other axis just loses its two walls.
    outer_span = L if split == "L" else W
    span = outer_span - 2 * T - (len(comps) - 1) * T
    across = (W if split == "L" else L) - 2 * T
    if span <= 0 or across <= 0 or H - F <= 0:
        raise ValueError(
            f"[{name}] outside {W} x {L} x {H} mm is too small for {T} mm walls "
            f"and {len(comps) - 1} divider(s)"
        )

    sizes = resolve_sizes(name, comps, span)
    over = 2.0  # overshoot so each cavity breaks through the top face

    cuts, placed, pos = [], [], T
    for comp, size in zip(comps, sizes):
        if size <= 0:
            raise ValueError(f"[{name}] compartment {comp['name']!r} sized {size}")
        depth = comp.get("depth")
        if depth is None:
            depth = H - F
        if not 0 < depth <= H - F:
            raise ValueError(
                f"[{name}] compartment {comp['name']!r} depth {depth} must be in "
                f"(0, {H - F}] to leave a floor under it"
            )

        z0 = H - depth  # raised floor when the compartment is shallow
        if split == "L":
            cuts.append(box((T, W - T), (pos, pos + size), (z0, H + over)))
        else:
            cuts.append(box((pos, pos + size), (T, L - T), (z0, H + over)))
        placed.append((comp["name"], size, depth, z0))
        pos += size + T

    mesh = trimesh.boolean.difference([box((0, W), (0, L), (0, H))] + cuts)
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_tray_{name}.stl"
    mesh.export(path)

    print("-" * 66)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm")
    print(
        f"    split     {len(comps)} compartments along {split}, "
        f"{len(comps) - 1} divider(s)"
    )
    print(f"    usable    {span:.1f} mm along {split}, {across:.1f} mm across")
    print("  Compartments")
    print(f"    {'name':<12}{'span':>8}{'depth':>8}{'floor z':>9}{'holds':>10}")
    for cname, size, depth, z0 in placed:
        print(
            f"    {cname:<12}{size:>8.1f}{depth:>8.1f}{z0:>9.1f}"
            f"{size * across * depth / 1000:>8.1f} ml"
        )
    print("  Mesh checks")
    print(f"    watertight  {mesh.is_watertight}")
    print(f"    bodies      {mesh.body_count}")
    print(f"    euler       {mesh.euler_number}")
    print(
        f"    volume      {mesh.volume / 1000:.1f} cm^3 "
        f"(~{mesh.volume * 1.24 / 1000:.0f} g)"
    )
    print(f"  -> {path}")
    print()
