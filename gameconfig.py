"""
Per-game parameter files, shared by both generators.

Every game keeps one file at games/<game_id>.json carrying the parameters
for everything printed for that game -- card holders and resource trays
alike. Both scripts take the game id as their only argument and read that
one file, so a dimension is stated once and only once.

Files declare the schema version they were written against. Bump
SCHEMA_VERSION whenever the shape below changes incompatibly; the loader
then refuses files it cannot read rather than silently misreading them.

Schema, version 7
-----------------
{
  "schema_version": 7,
  "game": {"id": str, "name": str},

  "card_holders": {                omit the whole section if none
    "wall": float,                 wall thickness
    "floor": float,                floor thickness
    "validation": {                optional, and every key in it optional
                                   too: none of this sizes anything, it only
                                   checks the cavity a variant's size left
                                   and estimates what will stack in it. What
                                   a section states here every variant takes
                                   unless it overrides it
      "sleeve": [W, L],            optional; the card the cavity is checked
                                   against -- and what the escape check
                                   measures the side opening against. Omit
                                   it and neither check runs
      "clearance": float,          optional, default 0; how much bigger than
                                   the sleeve the cavity has to come out
      "card_thickness": float      optional; omit it and the report skips
                                   the card count, giving mm of stack only
    },
    "emboss": {                    optional; what every label in this section
      "size": float,               starts from, holders and separators alike.
      "stroke": float,             Any key an emboss takes beyond its text,
      "height": float,             and a label saying null to one of them has
      "depth": float,              it worked out as if unset. height and depth
      "along": "W" | "L",          are the two ways a label can go, so state
      "leading": float             one or the other, never both
    },
    "separator": {                 what every separator takes unless it
      "thickness": float,          states its own
      "fit": float,                shrinks the sheet, and the tab, for a
                                   looser fit
      "tab_out": float | null      reach past the sheet; null means wall
    },                             tab length is not set here: it fills the
                                   variant's side opening, less the fit
    "variants": {
      "<name>": {
        "size": [W, L, H],         outside dimensions; the cavity is what is
                                   left inside the walls and over the floor
        "corner": float,           optional, default 0.2; the fraction of L
                                   each corner post keeps, so 0.2 leaves the
                                   middle 60% of each long wall open. Under
                                   0.5, and not so small that a post comes
                                   out thinner than a wall
        "separators": {            optional; one entry per sheet, keyed by
                                   an id that also names its STL. Every key
                                   inside is optional, so {} is a sheet on
                                   the section's numbers
          "<id>": {
            "thickness": float,    optional, default the section's
            "fit": float,          optional, default the section's
            "tab_out": float,      optional, default the section's
            "emboss": {...}        optional raised label on the sheet face,
                                   the same shape as elsewhere
          }
        },
        "validation": {            optional; the same three keys, each one
          "sleeve": [W, L],        standing in for the section's for this
          "clearance": float,      variant alone -- a holder taking a
          "card_thickness": float  different card states only what differs
        },
        "emboss": {...}            optional raised label on the cavity
                                   floor, under where the cards sit; the
                                   same shape as a tray compartment's,
                                   spelt out under trays below
      }
    }
  },

  "trays": {                       omit the whole section if none
    "wall": float,
    "floor": float,
    "emboss": {...},               optional; what every label in this section
                                   starts from, same four keys as above
    "variants": {
      "<name>": {
        "size": [W, L, H],         outside dimensions
        "split": "L" | "W",        axis the compartment row runs along
        "compartments": {          a row running along "split", laid out
                                   in the order the names are written
          "<name>": {              every key below is optional, so {} is a
                                   compartment that shares out what is left
            "size": float | null,  extent along this row's axis; leave it
                                   out, or null, to share out whatever the
                                   sized ones leave over
            "depth": float,        optional, default full inside depth; on a
                                   parent it becomes its children's default
            "compartments": {...}, optional; subdivides this compartment
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
            ],
            "openings": [          optional open sides: the whole wall taken
                                   out but a corner post each end, the way a
                                   card holder opens
              {
                "side": str,       which wall, as for a notch
                "corner": float,   optional, default 0.2; the fraction of
                                   that wall kept at each end, leaving the
                                   middle 60%. Under 0.5, and 0 takes the
                                   whole wall out
                "depth": float     optional, default the compartment's own
                                   depth, i.e. rim all the way to the floor
              }
            ],
            "emboss": {            optional raised label on this compartment's
                                   own floor; leaf compartments only, since a
                                   split one has no floor of its own
              "text": str | [str], what to put there: one string, a string
                                   with newlines in it, or a list of lines.
                                   Upper-cased, and every character must be
                                   one the stroke font has
              "size": float,       optional cap height; the default fits the
                                   compartment, up to 10 mm
              "stroke": float,     optional line width, default 14% of the cap
                                   and never under 0.8 mm
              "height": float,     optional stand-off from the floor, default
                                   0.6 mm; the label is raised
              "depth": float,      optional cut into the floor instead, this
                                   deep. Give height or depth, not both, and
                                   a cut leaves at least 0.4 mm under it
              "along": "W" | "L",  optional axis the text runs along, default
                                   whichever of the two is longer
              "leading": float     optional baseline-to-baseline spacing of
                                   several lines, in cap heights; the default
                                   is measured from the glyphs used, and 1.2
                                   is as tight as it goes
            }
          }
        }
      }
    }
  }
}
"""

import argparse
import glob
import json
import os
import shutil

import trimesh

SCHEMA_VERSION = 7
GAMES_DIR = "games"
MODELS_DIR = "models"


def parse_game_id(description):
    """Read the one required argument: which game to build for."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("game_id", help="game to build, i.e. the games/<id>.json stem")
    return ap.parse_args().game_id


def no_duplicate_keys(pairs):
    """Build an object, refusing a repeated key rather than keeping one.

    Names are load-bearing now -- they key compartments and separators, and
    a repeat would quietly drop everything but the last one, taking a
    compartment out of a tray without a word. JSON allows it; we do not.
    """
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(
                f"{key!r} appears twice in the same object -- names are how "
                f"compartments and separators are told apart, so a repeat "
                f"would silently drop one of them"
            )
        out[key] = value
    return out


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
            cfg = json.load(fh, object_pairs_hook=no_duplicate_keys)
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path} is not valid JSON: {e}") from None
        except ValueError as e:
            raise SystemExit(f"{path}: {e}") from None

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


def outdir(game_id, kind):
    """Empty models/<game_id>/<kind>/, made fresh for one generator's parts.

    A generator owns its subdirectory outright, so everything in it can go
    before the run rather than the run having to guess which files were its
    own by name. What is left afterwards is exactly what this run built:
    rename a variant, or drop one, and the STL it used to write goes with
    it instead of sitting in the folder waiting to be printed by mistake.
    """
    path = os.path.join(MODELS_DIR, game_id, kind)
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)
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
