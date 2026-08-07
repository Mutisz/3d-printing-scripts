"""
Per-game parameter files, shared by both generators.

Every game keeps one file at games/<game_id>.json carrying the parameters
for everything printed for that game -- card holders and resource trays
alike. Both scripts take the game id as their only argument and read that
one file, so a dimension is stated once and only once.

Files declare the schema version they were written against. Bump
SCHEMA_VERSION whenever the shape below changes incompatibly; the loader
then refuses files it cannot read rather than silently misreading them.

Schema, version 1
-----------------
{
  "schema_version": 1,
  "game": {"id": str, "name": str},

  "card_holders": {                omit the whole section if none
    "sleeve": [W, L],              sleeve size in mm
    "clearance": float,            added to the sleeve to get the cavity
    "wall": float,                 wall thickness
    "floor": float,                floor thickness
    "card_thickness": float,       for the capacity estimate
    "separator": {
      "thickness": float,
      "fit": float,                shrinks the sheet for a looser fit
      "tab_length": float,         tab length along L, centred
      "tab_out": float | null      reach past the sheet; null means wall
    },
    "variants": {
      "<name>": {
        "depth": float,            inside stack depth
        "corner": float,           wall fragment kept at each corner
        "pack_axis": "L" | "W",    dimension that repeats down a packed row
        "pack_count": int,
        "separators": int          optional, default 0
      }
    }
  },

  "trays": {                       omit the whole section if none
    "wall": float,
    "floor": float,
    "variants": {
      "<name>": {
        "size": [W, L, H],         outside dimensions
        "split": "L" | "W",        axis the compartment row runs along
        "compartments": [        a row running along "split"
          {
            "name": str,
            "size": float | null,  extent along this row's axis; null shares
                                   out whatever the sized ones leave over
            "depth": float,        optional, default full inside depth; on a
                                   parent it becomes its children's default
            "compartments": [...], optional; subdivides this compartment
                                   across the perpendicular axis, same shape
                                   as here, nestable to any depth
            "notches": [           optional finger slots, cut from the rim
              {
                "side": str,       which wall: "W-", "W+", "L-" or "L+",
                                   the low or high side on that axis. Any
                                   wall qualifies, dividers included.
                "width": float,    optional, default 60% of that wall
                "depth": float     optional, default half the compartment;
                                   measured down from the rim, and capped
                                   at the compartment's own depth
              }
            ]
          }
        ]
      }
    }
  }
}
"""

import argparse
import glob
import json
import os

import trimesh

SCHEMA_VERSION = 1
GAMES_DIR = "games"
MODELS_DIR = "models"


def parse_game_id(description):
    """Read the one required argument: which game to build for."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("game_id", help="game to build, i.e. the games/<id>.json stem")
    return ap.parse_args().game_id


def load_game(game_id):
    """Parse games/<game_id>.json, refusing anything of the wrong version."""
    path = os.path.join(GAMES_DIR, f"{game_id}.json")
    if not os.path.exists(path):
        known = sorted(
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(GAMES_DIR, "*.json"))
        )
        raise SystemExit(
            f"no parameter file at {path}\n"
            f"known games: {', '.join(known) if known else '(none yet)'}"
        )

    with open(path) as fh:
        try:
            cfg = json.load(fh)
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path} is not valid JSON: {e}") from None

    found = cfg.get("schema_version")
    if found != SCHEMA_VERSION:
        raise SystemExit(
            f"{path} declares schema_version {found!r} but this build of the "
            f"scripts reads version {SCHEMA_VERSION}"
        )
    return cfg


def need(mapping, key, where):
    """Fetch a required key, naming where it was missing from."""
    if key not in mapping:
        raise SystemExit(f"{where}: missing required key {key!r}")
    return mapping[key]


def outdir(game_id):
    """Per-game output directory, created if absent."""
    path = os.path.join(MODELS_DIR, game_id)
    os.makedirs(path, exist_ok=True)
    return path


def box(xr, yr, zr):
    """Axis-aligned box from three (min, max) ranges."""
    ext = [xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0]]
    ctr = [(xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2]
    return trimesh.creation.box(
        extents=ext, transform=trimesh.transformations.translation_matrix(ctr)
    )


def report_mesh(mesh, indent="    "):
    """The watertight / bodies / euler / volume block both scripts print."""
    print(f"{indent}watertight  {mesh.is_watertight}")
    print(f"{indent}bodies      {mesh.body_count}")
    print(f"{indent}euler       {mesh.euler_number}")
    print(
        f"{indent}volume      {mesh.volume / 1000:.1f} cm^3 "
        f"(~{mesh.volume * 1.24 / 1000:.0f} g)"
    )
