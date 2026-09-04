"""
Per-game parameter files, shared by every generator.

Every game keeps one file at games/<game_id>.json carrying the parameters
for everything printed for that game -- card wells, card boxes and
resource trays alike. Each script takes the game id as its only argument
and reads that one file, so a dimension is stated once and only once.

What the sections have in common lives here too, not in any one of them:
the validation block a card well and a card box are both checked
against, the dimension parsing under it, and the registry of every object
by id that the box layout is arranged out of.

Files declare the schema version they were written against. Bump
SCHEMA_VERSION whenever the shape below changes incompatibly; the loader
then refuses files it cannot read rather than silently misreading them.

Schema, version 10
------------------
{
  "schema_version": 10,
  "game": {"id": str, "name": str},

  "card_wells": {                  omit the whole section if none
    "wall": float,                 wall thickness
    "floor": float,                floor thickness
    "corner": float,               optional, default 0.2; the section's
                                   default for every variant's own corner
                                   below -- state it once here for a game
                                   whose wells all want the same post
                                   proportion, or leave it out and each
                                   variant falls back to 0.2 unless it says
                                   its own
    "validation": {                optional, and every key in it optional
                                   too: none of this sizes anything, it only
                                   checks the cavity a variant's size left
                                   and estimates what will stack in it. What
                                   a section states here every variant takes
                                   unless it overrides it
      "sleeve": [W, L],            optional; the card the cavity is checked
                                   against -- and what the escape check
                                   measures the end opening against. Omit
                                   it and neither check runs
      "clearance": float,          optional, default 0; how much bigger than
                                   the sleeve the cavity has to come out
      "card_thickness": float      optional; omit it and the report skips
                                   the card count, giving mm of stack only
    },
    "emboss": {                    optional; what every label in this section
      "size": float,               starts from, wells and separators alike.
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
                                   variant's end opening, less the fit
    "lid": {                       optional, and stating it at all is what
                                   gives every variant a lid: the notch a
                                   lid seats in is cut into the well, so
                                   it is the section's call, not one
                                   variant's. A lid closes the top of a
                                   well off so the next one up has
                                   nothing to fall into
      "thickness": float,          required; the sheet, which spans the
                                   cavity supported only at its two ends,
                                   so 1.5 mm and up on a long cavity
      "fit": float,                optional, default the separator's;
                                   shrinks the sheet and its open-end tab
      "notch": float,              optional, default 0.3; the fraction of
                                   the closed end wall the tab takes, as
                                   corner is a fraction of the open end's.
                                   Under 1, and no wider than the cavity,
                                   or it would cut into that wall's own
                                   corners
      "notch_fit": float,          optional, default 0.6; how much wider
                                   than its tab the notch is cut, in all.
                                   Slop here is invisible, while a pinched
                                   tab holds the lid proud of the rim
      "seat": float,               optional, default 0.2; how far under the
                                   rim the lid lands. The notch is cut
                                   thickness + seat deep, and that much
                                   comes off the top of the card stack
      "emboss": {...}              optional label cut into the lid, the
                                   same shape as elsewhere but depth only.
                                   Left out, the lid takes the well's own
                                   label, so a stack reads from outside
    },
    "variants": {
      "<name>": {
        "size": [W, L, H],         outside dimensions; the cavity is what is
                                   left inside the walls and over the floor
        "corner": float,           optional, default the section's, or 0.2
                                   if the section states none; the fraction
                                   of W each corner post keeps at the open
                                   end, so 0.2 leaves the middle 60% of that
                                   end open. Under 0.5, and not so small
                                   that a post comes out thinner than a wall
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
          "clearance": float,      variant alone -- a well taking a
          "card_thickness": float  different card states only what differs
        },
        "lid": bool | {...},       optional; only meaningful where the
                                   section states a lid, and then only to
                                   disagree with it. false for a well
                                   that goes without one, true for one on
                                   the section's numbers, or the same keys
                                   again for what differs
        "emboss": {...}            optional raised label on the cavity
                                   floor, under where the cards sit; the
                                   same shape as a tray compartment's,
                                   spelt out under trays below
      }
    }
  },

  "card_boxes": {                  omit the whole section if none
                                   A closed sleeve rather than a well: solid
                                   floor, ceiling, both long walls and one
                                   short wall, with the other short wall
                                   missing altogether. Stated lying down, as
                                   it sits in an insert, and written out
                                   standing on its closed end, as it prints
                                   -- so the STL measures W x H x L
    "wall": float,                 the two long walls and the closed end
    "floor": float,                the face the cards rest on
    "ceiling": float,              optional, default the floor; the face the
                                   slot and the label are in
    "validation": {...},           optional; the same three keys a card
                                   holder is checked against, inherited the
                                   same way. There is no escape check here:
                                   the mouth is open on purpose
    "emboss": {...},               optional; what every label in this section
                                   starts from, the same keys as elsewhere
    "notch": {                     optional; the thumb slots, one in the
                                   ceiling and the same one in the floor, so
                                   the stack can be pinched from both sides.
                                   In mm rather than a fraction, because a
                                   thumb is one size whatever the card is
      "width": float,              optional, default 25.0; across W, centred,
                                   and no wider than the cavity
      "reach": float               optional, default 25.0; back from the
                                   mouth, and short of the closed end. The
                                   end is rounded, semicircular once the
                                   reach is half the width or more
    },
    "variants": {
      "<name>": {
        "size": [W, L, H],         outside, lying down: W across, L from the
                                   closed end to the mouth, H the stack
        "notch": {...},            optional, standing in for the section's
        "validation": {...},       optional, standing in for the section's
        "emboss": {...}            optional label on the ceiling, clear of
                                   its slot; the same shape as elsewhere.
                                   The floor is slotted alike but never
                                   labelled
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
            "depth": float,        optional, default full inside depth; 0
                                   leaves the compartment filled solid to
                                   the rim, as a spacer; on a parent it
                                   becomes its children's default
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
                                   card well opens
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
  },

  "box": {                         omit the whole section if the game box
                                   has not been laid out yet. Nothing here
                                   builds anything either: it states where
                                   every part goes once the printing is
                                   done, so check_box.py can say whether it
                                   all fits rather than you working it out
                                   again every time a tray is resized
    "size": [W, L, H],             inside the game box, in the same frame
                                   as everything else in this file:
                                     W  across the box
                                     L  along the box
                                     H  up the box
    "clearance": float,            optional, default 0; slack taken off
                                   each axis in total, for a box that is
                                   never quite its nominal size
    "extras": {                    optional; what is in the box that no
                                   script here prints -- boards, rulebooks,
                                   bagged bits. They are placed by id like
                                   any part, and checked like one
      "<id>": {
        "size": [W, L, H],         outside, as it lies in the box
        "note": str                optional, printed beside it in the report
      }
    },
    "place": [                     the arrangement. These follow each other
                                   across W, in written order. Each entry
                                   is an object id -- any card_wells,
                                   card_boxes or trays variant, or an
                                   extras entry -- an object, or a run of
                                   entries along an axis of its own:
      "<id>",
      {
        "id": str,                 which object
        "turn": bool               optional, default false; lay it across,
                                   swapping its W and its L
      },
      {
        "along": str,              "W", "L" or "H": which way this run
                                   goes. Its entries follow each other
                                   along that axis from the corner the run
                                   was handed, and start together on the
                                   other two. The run is as long as they
                                   come to along that axis, and as wide
                                   and as tall as the widest and tallest
                                   thing in it
        "size": float,             optional extent along "along"; the
                                   default is a tight fit around the run's
                                   own contents
        "place": [ ... ]           the same list again -- ids, objects,
                                   gaps, or further runs
      },
      {
        "gap": float               space left deliberately empty, this
                                   many mm along whatever run holds it.
                                   It holds nothing and is checked for
                                   nothing; it is there so that what
                                   follows starts clear of a corner that
                                   has no object in it to push it past
      }
    ]
  }
}

Nothing states a position. An entry starts where the entry before it in
the same run ends, so resizing a tray moves what is stacked on it and
leaves the rest of the box alone. Runs hold runs, so the box is described
to whatever depth it actually has.

An object is named once. Where it goes is the arrangement's business, and
the arrangement already says.

Everything takes its position from what is written before it, so something
standing over an empty corner has nothing to push it clear of that corner.
A gap is what to write there.
"""

import argparse
import glob
import json
import os
import shutil

import trimesh

SCHEMA_VERSION = 10
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


def dims(value, count, at, what):
    """A list of `count` positive numbers, or a message naming the key."""
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        out = None
    if out is None or len(out) != count:
        raise SystemExit(f"{at}: {what} must be {count} numbers in mm, got {value!r}")
    if any(v <= 0 for v in out):
        raise SystemExit(f"{at}: {what} must be positive, got {value!r}")
    return out


# Nothing under validation builds anything. A sleeve is what the cavity is
# checked against, clearance how much bigger than it the cavity has to come
# out, and card_thickness what the capacity estimate counts in -- so a
# section states them for every variant, a variant overrides the ones it
# disagrees with, and a part with none stated comes out exactly the same,
# just unchecked. A card well and a card box are checked the same way,
# which is why this lives here rather than in either of them.
VAL_KEYS = ("sleeve", "clearance", "card_thickness")


def validation(spec, at):
    """The validation block a section or a variant states.

    Closed to those three keys: this block is inherited silently, so a typo
    in it would otherwise turn a check off without ever saying so.
    """
    block = spec.get("validation") or {}
    if not isinstance(block, dict):
        raise ValueError(f"{at} validation: must be an object, got {block!r}")
    unknown = [key for key in block if key not in VAL_KEYS]
    if unknown:
        named = ", ".join(repr(key) for key in unknown)
        raise ValueError(
            f"{at} validation: {named} is not something a part is checked "
            f"against -- it takes {', '.join(VAL_KEYS)}"
        )
    stray = [key for key in VAL_KEYS if key in spec]
    if stray:
        named = ", ".join(repr(key) for key in stray)
        raise ValueError(
            f"{at}: {named} goes inside validation, not beside it -- left out "
            f"here it would be read as nothing at all, quietly dropping the "
            f"check it was written for"
        )
    return block


def checks_of(spec, at, section):
    """What a variant is checked against: its own words over the section's.

    Every key is optional at either level, and a missing one is not an error
    -- it only means there is nothing to check that against. Returns the
    sleeve, the clearance, the card thickness, and the block the variant
    stated itself, which is what the report marks as its own.
    """
    own = validation(spec, at)
    checks = {**section, **own}

    sleeve = checks.get("sleeve")
    if sleeve is not None:
        sleeve = dims(sleeve, 2, at, "sleeve")

    clear = checks.get("clearance", 0.0)
    if clear < 0:
        raise ValueError(
            f"{at} validation: clearance is room demanded over the sleeve, so "
            f"it cannot be negative, got {clear}"
        )

    thick = checks.get("card_thickness")
    if thick is not None and thick <= 0:
        raise ValueError(
            f"{at} validation: card_thickness must be positive to estimate a "
            f"stack from, got {thick}"
        )
    return sleeve, clear, thick, own


def own_note(own, *keys):
    """Flag a report line whose numbers the variant overrode itself."""
    return "   (this variant only)" if any(key in own for key in keys) else ""


# Every part a generator writes, plus everything the box holds that none of
# them do, under one flat set of ids -- which is what a layout arranges. It
# lives here for the reason validation() does: no one section owns it, and
# the uniqueness it needs has to hold across all four at once.
PART_SECTIONS = ("card_wells", "card_boxes", "trays")


def tabs_proud(wells, spec):
    """How far a well's separator tabs stand past its stated L, at the open end.

    A separator's tab reaches `tab_out` out from the cavity wall, so it
    clears the outside of the well by whatever that is over the wall
    thickness -- and a well in a box is as long as its tab, not as long as
    its size says, when that tab reaches past flush. `null`, the usual
    setting, lands the tab flush and adds nothing. A lid never protrudes:
    its own open-end tab is built a wall out on purpose, to fill the rim,
    which is the same flush amount a default separator tab already is.
    """
    wall = wells.get("wall")
    if wall is None:
        return 0.0
    fallback = (wells.get("separator") or {}).get("tab_out")
    outs = [
        sheet.get("tab_out", fallback)
        for sheet in (spec.get("separators") or {}).values()
        if isinstance(sheet, dict)
    ]
    return max([0.0] + [out - wall for out in outs if out is not None])


def object_sizes(cfg, where):
    """Every object a box layout can place, by id: size, source and note.

    Ids are flat across the file, since a layout names an object by id
    alone. That is only safe if it is checked, so a name used twice is
    refused here rather than one of the pair quietly winning.
    """
    found = {}

    def add(oid, size, at, note=None):
        if oid in found:
            raise SystemExit(
                f"{where}: {oid!r} is defined twice, at {found[oid]['where']} "
                f"and at {at} -- a box layout names an object by its id alone, "
                f"so the two cannot be told apart. Rename one of them"
            )
        found[oid] = {"size": size, "where": at, "note": note}

    for section in PART_SECTIONS:
        block = cfg.get(section) or {}
        for name, spec in (block.get("variants") or {}).items():
            at = f"{section}.variants.{name}"
            size = dims(need(spec, "size", f"{where} {at}"), 3, f"{where} {at}", "size")
            note = None
            if section == "card_wells":
                proud = tabs_proud(block, spec)
                if proud > 0:
                    size = [size[0], size[1] + proud, size[2]]
                    note = f"L includes {proud:.1f} mm of tab standing proud"
            add(name, size, at, note)

    for name, spec in ((cfg.get("box") or {}).get("extras") or {}).items():
        at = f"box.extras.{name}"
        if not isinstance(spec, dict):
            raise SystemExit(f"{where} {at}: must be an object, got {spec!r}")
        unknown = [key for key in spec if key not in ("size", "note")]
        if unknown:
            named = ", ".join(repr(key) for key in unknown)
            raise SystemExit(
                f"{where} {at}: {named} is not something an extra takes -- it "
                f"is only a size and, if you want one, a note"
            )
        size = dims(need(spec, "size", f"{where} {at}"), 3, f"{where} {at}", "size")
        add(name, size, at, spec.get("note"))

    return found


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
