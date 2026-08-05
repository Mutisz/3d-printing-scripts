"""
Card holders: top-loaded tray, open top, open long sides.

Cards lie flat and stack upward, dropped in through the open top. The floor
and the two short end walls are solid and full height. The two long walls
are gone but for a short fragment at each corner -- four posts that leave
the long sides open to reach in from.

Those openings are shorter than a card's 91 mm length, so the corner posts
block a card from sliding straight out sideways; it would have to rotate
first. Access without escape.

Either packing axis is fine; pack_axis names the dimension that repeats
down the row. "L" butts the solid end walls together, so every holder keeps
both long sides exposed and cards stay reachable while boxed. "W" butts the
open long sides together for a shorter row -- access is blocked in the box,
which costs nothing when the holders come out to play.

Sleeves measured at 67 x 91 mm.
"""

import os

import trimesh

# ---- Parameters -------------------------------------------------------
SLEEVE_W, SLEEVE_L = 67.0, 91.0
CLEAR = 1.0  # clearance between cards and walls
T = 1.0  # wall thickness
F = 1.0  # floor thickness
CARD_THICK = 0.6  # for the capacity estimate

GAME_ID = "cafe_baras"
# name -> variant spec.
#   depth       inside stack depth
#   corner      length of the wall fragment kept at each corner, along L
#   pack_axis   dimension that repeats down a packed row, so the row length
#               is pack_count * that: "L" (94 mm, end walls meet) or
#               "W" (70 mm, open long sides meet)
VARIANTS = {
    "main_deck": {
        "depth": 30.0,
        "corner": 10.0,
        "pack_axis": "W",
        "pack_count": 2,
    },
    "cafes_and_customers": {
        "depth": 20.0,
        "corner": 10.0,
        "pack_axis": "W",
        "pack_count": 1,
    },
}

OUTDIR = f"./models/{GAME_ID}"
# -----------------------------------------------------------------------

INNER_W = SLEEVE_W + CLEAR
INNER_L = SLEEVE_L + CLEAR
W = INNER_W + 2 * T
L = INNER_L + 2 * T


def box(xr, yr, zr):
    ext = [xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0]]
    ctr = [(xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2]
    return trimesh.creation.box(
        extents=ext, transform=trimesh.transformations.translation_matrix(ctr)
    )


os.makedirs(OUTDIR, exist_ok=True)

print("=" * 60)
print("Card Holder Generator")
print("=" * 60)
print("Shell")
print(f"  sleeve      {SLEEVE_W} x {SLEEVE_L} mm + {CLEAR} mm clearance")
print(f"  inside      {INNER_W} x {INNER_L} mm")
print(f"  outside     {W} x {L} mm")
print(f"  thickness   {T} mm walls, {F} mm floor")
print()

for name, spec in VARIANTS.items():
    depth, corner = spec["depth"], spec["corner"]
    pack_axis, pack_count = spec["pack_axis"], spec["pack_count"]

    if pack_axis not in ("L", "W"):
        raise ValueError(f"[{name}] pack_axis must be 'L' or 'W', got {pack_axis!r}")
    if not T <= corner < L / 2:
        raise ValueError(
            f"[{name}] corner must be in [{T}, {L / 2}) to leave posts and an "
            f"opening between them, got {corner}"
        )

    H = F + depth
    row_w = pack_count * W if pack_axis == "W" else W
    row_l = pack_count * L if pack_axis == "L" else L
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
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    path = f"{OUTDIR}/{GAME_ID}_card_holder_{name}.stl"
    mesh.export(path)

    opening = L - 2 * corner
    trapped = opening < SLEEVE_L

    print("-" * 60)
    print(f"[{name}]")
    print("  Dimensions")
    print(f"    outside   {W} x {L} x {H} mm")
    print(f"    stack     {depth} mm deep")
    print(
        f"    packing   {pack_count} repeated along {pack_axis} -> "
        f"{row_w:.1f} x {row_l:.1f} mm row"
    )
    print("  Long sides")
    print(f"    posts     {corner} mm at each corner, full height, {T} mm thick")
    print(f"    opening   {opening} mm long, floor to rim ({depth} mm tall)")
    print(
        f"    check     {opening} mm opening vs {SLEEVE_L} mm card -> "
        f"{'OK, card cannot slide out' if trapped else 'CARD CAN ESCAPE'}"
    )
    print("  Mesh checks")
    print(f"    watertight  {mesh.is_watertight}")
    print(f"    bodies      {mesh.body_count}")
    print(f"    euler       {mesh.euler_number}")
    print(
        f"    volume      {mesh.volume / 1000:.1f} cm^3 "
        f"(~{mesh.volume * 1.24 / 1000:.0f} g)"
    )
    print("  Capacity")
    print(f"    ~{depth / CARD_THICK:.0f} sleeved cards")
    print(f"  -> {path}")
    print()
