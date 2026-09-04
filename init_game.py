"""
Scaffold a parameter file for a game that has none yet.

Writes games/<game_id>.json holding one worked example of each thing the
schema describes -- a card well, a card box, a tray, and a box layout
placing all three -- using the keys that earn their place in the files
already here, rather than every key there is. The numbers are made up.
What comes out loads and, as it stands, even fits; none of it is measured
off a real game, so it is a shape to edit rather than a design.

The schema itself is documented field by field in the gameconfig
docstring, JSON having no comments to carry that here. The version
stamped into the file comes from there too, so a template cannot be
written against a schema this build would then refuse to read.

An existing file is never overwritten. A parameter file is the source of
truth for everything printed for that game, and re-running this on a game
already described would trade all of it for a fake, so it refuses instead.

Run as: python3 init_game.py <game_id>
"""

import json
import os
import re

from gameconfig import GAMES_DIR, SCHEMA_VERSION, parse_game_id


# A dimension is read as a dimension, not as a column of numbers, so the
# arrays go back on one line after the encoder has spread them out -- the
# way every file already in games/ is written by hand. Each candidate is
# re-parsed before it is collapsed, so anything the pattern clipped short
# is left exactly as it was rather than rewritten wrong.
FLAT = re.compile(r"\[[^][{}]*?\]", re.S)


def one_line_arrays(text):
    """Put every array of plain values back on the line its key is on."""

    def collapse(match):
        try:
            return json.dumps(json.loads(match.group(0)), ensure_ascii=False)
        except json.JSONDecodeError:  # not a whole array: leave it alone
            return match.group(0)

    return FLAT.sub(collapse, text)


def template(game_id):
    """One of everything, on invented numbers, for `game_id` to start from."""
    return {
        "schema_version": SCHEMA_VERSION,
        "game": {
            "id": game_id,
            "name": game_id.replace("_", " ").title(),
        },
        "card_wells": {
            "wall": 1.0,
            "floor": 1.0,
            "corner": 0.2,
            "validation": {
                "clearance": 1.0,
                "card_thickness": 0.6,
            },
            "emboss": {
                "depth": 0.4,
            },
            "separator": {
                "thickness": 1.0,
                "fit": 0.2,
            },
            "variants": {
                "main_deck": {
                    "size": [70.0, 94.0, 30.0],
                    "validation": {"sleeve": [66.0, 90.0]},
                    "emboss": {"text": "MAIN DECK"},
                    "separators": {
                        "expansion": {"emboss": {"text": "EXPANSION"}}
                    },
                }
            },
        },
        "card_boxes": {
            "wall": 1.0,
            "floor": 1.0,
            "ceiling": 1.0,
            "validation": {
                "sleeve": [66.0, 90.0],
                "clearance": 1.0,
                "card_thickness": 0.6,
            },
            "emboss": {
                "along": "W",
                "size": 7.0,
                "depth": 0.5,
            },
            "notch": {
                "width": 25.0,
                "reach": 20.0,
            },
            "variants": {
                "reference_cards": {
                    "size": [70.0, 94.0, 20.0],
                    "emboss": {"text": "REFERENCE"},
                }
            },
        },
        "trays": {
            "wall": 1.0,
            "floor": 1.0,
            "emboss": {
                "depth": 0.4,
            },
            "variants": {
                "tokens": {
                    "size": [70.0, 120.0, 25.0],
                    "split": "L",
                    "compartments": {
                        "coins": {
                            "size": 40.0,
                            "depth": 12.0,
                            "emboss": {"text": "COINS"},
                        },
                        "cubes": {
                            "size": 40.0,
                            "compartments": {
                                "wood": {},
                                "stone": {},
                            },
                        },
                        "misc": {
                            "size": None,
                            "notches": [{"side": "L+"}],
                            "emboss": {"text": "MISC"},
                        },
                    },
                }
            },
        },
        "box": {
            "size": [244.0, 244.0, 60.0],
            "clearance": 1.0,
            "extras": {
                "rulebook": {
                    "size": [210.0, 240.0, 8.0],
                    "note": "nothing here prints this -- it is placed, not made",
                }
            },
            "place": [
                {
                    "along": "H",
                    "place": [
                        "rulebook",
                        {
                            "along": "L",
                            "place": [
                                {
                                    "along": "W",
                                    "place": ["main_deck", "reference_cards"],
                                },
                                "tokens",
                            ],
                        },
                    ],
                }
            ],
        },
    }


GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
PATH = os.path.join(GAMES_DIR, f"{GAME_ID}.json")

if os.path.exists(PATH):
    raise SystemExit(
        f"{PATH} already exists -- it is the source of truth for everything "
        f"printed for {GAME_ID}, and this would replace it with invented "
        f"numbers. Delete it yourself if that is really what you want"
    )

os.makedirs(GAMES_DIR, exist_ok=True)
TEXT = json.dumps(template(GAME_ID), indent=2, ensure_ascii=False)
with open(PATH, "w") as fh:
    fh.write(one_line_arrays(TEXT) + "\n")

print(f"wrote {PATH}, schema version {SCHEMA_VERSION}")
print(
    "  every number in it is invented: edit it against the real components "
    "before printing anything"
)
print("  the field-by-field reference is the gameconfig.py docstring")
print(f"  then: python3 make_all.py {GAME_ID}")
