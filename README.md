# 3d-printing-scripts

Parametric generators for 3D-printable board game inserts. Each script builds
its meshes with [trimesh](https://trimesh.org) boolean operations and exports
STLs ready to slice.

## Scripts

| Script | Makes |
| --- | --- |
| [init_game.py](init_game.py) | Not a generator — scaffolds `games/<game_id>.json` for a game that has none yet, with one worked example of each thing the schema describes |
| [make_all.py](make_all.py) | Every generator below, in turn, for one game, then the fit check |
| [make_card_well.py](make_card_well.py) | Top-loaded card trays — solid floor and three walls, the fourth open at the middle between two corner posts so cards stay reachable but cannot slide out. Plus matching card separators, if the game asks for them |
| [make_card_box.py](make_card_box.py) | Closed card sleeves — floor, ceiling, both long walls and one short one, with the far end left open so a deck slides in and out. Thumb slots top and bottom to pinch the stack back out |
| [make_resource_tray.py](make_resource_tray.py) | Open-top trays split into a row of compartments, with exact outside dimensions, optional raised floors for small pieces, and walls that can be notched or opened out entirely |
| [check_box.py](check_box.py) | Not a generator — works out where every part lands in the game box and says whether it all fits, then draws it |
| [boxlayout.py](boxlayout.py) | Not a generator — the placement and fit arithmetic that check does |
| [gameconfig.py](gameconfig.py) | Not a generator — loads the per-game parameter files and documents their schema |
| [label.py](label.py) | Not a generator — sizes and builds the embossed labels both generators offer |
| [stroke_font.py](stroke_font.py) | Not a generator — the single-stroke font those labels are drawn with |

## Usage

Open the repo in the dev container (see below) and the dependencies are already
there. Otherwise, install them yourself:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Every script takes one argument, the game to build:

```bash
python init_game.py new_game            # start a game off with a parameter file
python make_all.py cafe_baras           # everything for that game
python make_card_well.py cafe_baras     # or just one generator
python make_resource_tray.py cafe_baras
python check_box.py cafe_baras          # does it all fit in the box?
```

Each generator prints what it built — outside and inside dimensions, then the
compartments or the card capacity — and writes STLs to its own folder under
`./models/<game_id>/`:

```
models/cafe_baras/
├── card_wells/     written by make_card_well.py
├── card_boxes/     written by make_card_box.py
├── trays/          written by make_resource_tray.py
└── box/            written by check_box.py — the packing preview
```

`models/` is git-ignored — the parameter files are the source of truth, the
models are output.

Each generator **empties its own folder before it builds**, so what is in there
afterwards is exactly what that run produced. Rename a variant, or delete one,
and the STL it used to write goes with it rather than lingering to be printed by
mistake. Nothing else should be kept in those folders. The wipe happens even
when there is nothing to build, so removing a whole section from the parameter
file clears the parts it used to make.

`make_all.py` runs each of them in turn and prints nothing of its own — the
report you see is theirs. A game that defines no trays (or no card wells, or
no box layout) is not an error: the script with nothing to do says so and exits
clean. Any other failure stops the run where it happened — the scripts that
would have followed are not started — and `make_all.py` exits with the failing
one's code. The fit check goes last, so a layout that does not hold still
leaves you the STLs it was complaining about.

## Configuring

Parameters live in one JSON file per game, `games/<game_id>.json`, holding both
the card wells and the trays for that game. Nothing is configured by editing
the scripts.

`python init_game.py <game_id>` writes a starting point: one card well, one
card box, one tray and a box layout placing all three, using the keys that get
used in practice rather than every key there is. Every number in it is invented
— it builds and it fits, but it describes no real game, so measure your
components and edit it down. It refuses to overwrite a file that already
exists.

Each file declares the `schema_version` it was written against, and the loader
refuses a version it does not understand rather than misreading it. The schema
is documented in full in the [gameconfig.py](gameconfig.py) docstring — JSON has
no comments, so that is where the field-by-field reference lives.

Sketch:

```jsonc
{
  "schema_version": 10,
  "game": { "id": "cafe_baras", "name": "Cafe Baras" },
  "card_wells": {
    "wall": 1.0, "floor": 1.0, "corner": 0.11,
    "validation": { "sleeve": [67.0, 91.0], "clearance": 1.0, "card_thickness": 0.6 },
    "separator": { "thickness": 1.0, "fit": 0.2, "tab_out": null },
    "variants": { "main_deck": { "size": [70.0, 94.0, 31.0],
                                 "separators": { "age-i": {}, "age-ii": {} } } }
  },
  "trays": {
    "wall": 1.0, "floor": 1.0,
    "variants": { "coins": { "size": [70.0, 94.0, 21.0], "split": "L",
                             "compartments": { "1": {}, "5": { "size": 30.0 } } } }
  },
  "box": {
    "size": [244.0, 244.0, 50.0],
    "place": ["main_deck", "coins"]
  }
}
```

Any top-level section may be omitted. Every script validates what it reads and
fails with a message naming the conflict — and the offending key's path in the
file — rather than exporting a bad mesh.

### Outside dimensions, and the `validation` block

Card wells are stated the way trays are: `size` is the outside `[W, L, H]`,
because that is the hard constraint when the thing has to drop into a box. The
cavity is whatever is left inside the walls and over the floor.

Nothing under `validation` takes part in that. Those three keys only check what
the size already decided, or estimate what will stack in it, so a well built
with the block deleted comes out byte for byte the same — just unchecked.

```jsonc
"card_wells": {
  "validation": {                              // every variant starts here
    "sleeve": [67.0, 91.0],                    // the card the cavity is checked against
    "clearance": 1.0,                          // room it must have over that sleeve
    "card_thickness": 0.6                      // what the capacity estimate counts in
  },
  "variants": {
    "main_deck":  { "size": [70.0, 94.0, 31.0], /* ... */ },
    "mini_cards": { "size": [48.0, 71.0, 21.0],
                    "validation": { "sleeve": [45.0, 68.0] }, /* ... */ }
  }
}
```

A variant's `validation` is merged over the section's key by key, so a well
taking a different card states only what differs — `mini_cards` above keeps the
section's clearance and card thickness and swaps the sleeve alone. Report lines
built from a variant's own numbers are marked `(this variant only)`.

Every key is optional at both levels. State a `sleeve` and the cavity is checked
against it, the report saying how much room is left over, and a cavity too small
for the sleeve plus `clearance` stops the build; `clearance` is that demanded
margin, in total across each axis, and defaults to 0. The escape check — is the
end opening shorter than a card? — needs a sleeve too, and stops the build the
same way, naming the smallest `corner` that would keep the card in.
`card_thickness` only feeds the "~N sleeved cards" estimate; without it the
report gives the stack in mm and leaves the count out.

### Separators

Separators are named rather than counted. Each key under a variant's
`separators` is one sheet and one STL, and each entry states only what it wants
of its own — an empty object takes the section's numbers for everything.

```jsonc
"card_wells": {
  "separator": { "thickness": 1.0, "fit": 0.2, "tab_out": null },  // defaults
  "variants": {
    "main_deck": { "separators": {
        "age-i":   { "emboss": { "text": "AGE I" } },
        "age-ii":  { "emboss": { "text": "AGE II" }, "thickness": 1.6 },
        "spare":   {}                                // all of the above
    }}
  }
}
```

`thickness`, `fit` and `tab_out` override the `separator` section per sheet, and
`emboss` raises a label on the sheet face — the same label option compartments
and wells take. The id names the file, so `age-i` above comes out as
`<game>_card_separator_main_deck_age-i.stl`.

A sheet's tab is not configured. It fills the end opening its well actually
has — `W` less the two corner posts — minus the same `fit` that shrinks the
sheet, so the tab is as wide as it can be, reaches through the opening
whatever the corner posts are set to, and cannot fall out of step with them.
`tab_out` still sets how far it stands proud; `null` means flush with the
outer wall.

Every sheet is written as its own STL, and their combined thickness comes off
the depth available for cards, which the capacity lines report.

### Compartments

A tray's `compartments` is an object: each key names a compartment, and they sit
in the row **in the order they are written**. Every key inside an entry is
optional, so `{}` is a complete compartment — one that shares out whatever the
sized ones leave over. A row of empty objects divides a tray evenly:

```jsonc
"compartments": { "red": {}, "green": {}, "blue": {} }
```

Names have to be unique within their row, and a repeated name is refused rather
than quietly dropping one of the pair — it is the one mistake this shape makes
easy, so the loader checks for it across the whole file.

### Nested compartments

A tray compartment that carries `compartments` of its own is subdivided across
the *perpendicular* axis, so a row along `L` becomes columns along `W`. Nest as
deep as you like; the axis flips at every level, which is what turns nesting
into a grid. `depth` set on a parent becomes the default for everything under
it.

```jsonc
"compartments": {
  "cubes": { "size": 40.0, "depth": 10.0, "compartments": {
      "red":   {},                    // three equal columns,
      "green": {},                    // each 10 mm deep
      "blue":  {}
  }},
  "coins": {}                         // full-depth, rest of the tray
}
```

A `depth` of 0 is the other end of the same knob: the compartment is filled
solid to the rim, so it is a spacer holding its neighbours where you want them
rather than somewhere to put anything. It takes no `notches` or `openings` —
there is no cavity for either to reach into.

### Notches

Any compartment, at any nesting level, can have rounded finger slots cut down
from the rim through a named wall. `side` picks the wall — `"W-"`, `"W+"`,
`"L-"` or `"L+"`, the low or high side on that axis — and every wall qualifies,
internal dividers included.

```jsonc
"notches": [
  { "side": "L+", "width": 20.0, "depth": 8.0 },
  { "side": "W-" }                          // width and depth defaulted
]
```

`width` defaults to 60% of that wall's length, `depth` to half the
compartment's, measured down from the rim and capped at the compartment's own
depth. A notch on an outer wall opens to the outside; one on a divider opens a
channel to the neighbour, so it stops short of the floor unless you push
`depth` all the way.

Nothing overhangs — a notch only removes material from the rim down, leaving a
shorter wall — so trays still print without supports.

### Open sides

When a notch is not enough, `openings` takes the whole wall out instead — rim
to floor, over the wall's whole length bar a post left standing at each end.
That is the card well's open end, in a tray: reach in from the side and lift
a stack straight out, while the posts keep it from sliding out on its own.

```jsonc
"compartments": {
  "event_tiles": { "size": 46.0, "openings": [
      { "side": "L-", "corner": 0.25 },      // post a quarter of the wall each end
      { "side": "L+", "corner": 0.25 }
  ]},
  "pawns": { "openings": [
      { "side": "L+" }                       // corner defaulted
  ]}
}
```

`side` names the wall exactly as a notch does, dividers included. `corner` is
the fraction of that wall kept at each end — not a length in mm, so a post keeps
its proportion however wide the compartment comes out — and defaults to `0.2`,
leaving the middle 60% open, the same span a notch defaults to. It has to be
under `0.5`, or there is nothing left between the posts; set it to `0` to take
the wall out entirely.

The card well's `corner` is the same setting under another roof, and takes the
same default: state it as a fraction of `W`, or get `0.2` at each end and the
middle 60% of the well's one open end open. It can be defaulted for the whole
`card_wells` section too, the way `separator` and `emboss` already are, rather
than repeated on every variant. There it also has to leave a post at least
one wall thick, since a post thinner than the wall it stands in is no post, and
— where a `sleeve` is stated — an opening shorter than the card, or the well
would not hold it.

`depth` defaults to the compartment's own depth, so the opening runs all the way
down to the floor; give it a smaller number to leave a lip standing. Either way
the cut only removes material downward from the rim, so this prints without
supports too.

Size the posts against what is inside: an opening shorter than the piece it
holds cannot let that piece out sideways. On a divider, a full-depth opening
merges the two compartments into one.

### Embossed labels

Any compartment with a floor of its own can have a label raised off it, so a
tray comes out of the box knowing what goes where. A card well takes the same
option on its variant, which puts the label on the cavity floor, under where the
cards sit — an empty well still says which deck it belongs to.

```jsonc
"compartments": {
  "coins": { "size": 40.0, "emboss": { "text": "COINS" } },
  "wood":  { "emboss": {
      "text": "WOOD", "size": 6.0, "height": 1.0, "along": "L" } }
}
```

`text` is all that is required. The label sizes itself to the compartment — up
to a 10 mm cap, since a label is a label — and turns to run along whichever axis
has more room, so a tray full of them needs no numbers typed per compartment.

| key | default |
| --- | --- |
| `size` | cap height that fits the compartment, capped at 10 mm |
| `stroke` | 14% of the cap height, never finer than 0.8 mm |
| `height` | 0.6 mm standing off the floor |
| `depth` | — cut into the floor instead of raised off it |
| `along` | `"W"` or `"L"`, whichever way the compartment is longer |
| `leading` | line spacing measured from the glyphs used, never under 1.2 |

Those four can be defaulted for a whole section, the way `separator` defaults
its sheets, so a game can be labelled in one house style without repeating the
numbers on every compartment:

```jsonc
"trays": {
  "wall": 1.0, "floor": 1.0,
  "emboss": { "size": 5.0, "stroke": 0.9, "along": "L" },   // every label here
  "variants": { /* ... */ }
}
```

A label's own word wins over the section's, and `null` sends a key back to
being worked out — so `{ "text": "AUTO", "size": null }` sizes itself to its
compartment even under a section that states a size. `card_wells.emboss`
works the same and covers both the well floor and its separators. The block
takes only those four keys: `text` belongs to the label, and anything else —
a typo included — is refused rather than silently ignored.

```jsonc
"card_wells": {
  "variants": {
    "main_deck": { "size": [70.0, 94.0, 31.0], "emboss": { "text": "MAIN DECK" } }
  }
}
```

`text` can be several lines — a list, or one string with newlines in it:

```jsonc
"victory_points": { "emboss": { "text": ["VICTORY", "POINTS"] } },
"trade_fleets":   { "emboss": { "text": "TRADE\nFLEETS" } }
```

Lines are centred on each other, and the block is sized to the compartment as a
whole, so two lines simply come out smaller than one would. Spacing is measured
from the glyphs actually used: plain capitals sit tight, a line carrying `Ą` or
`Ó` is given the room those need, and a blank line in the middle spaces the
lines around it. `leading` overrides the measurement, in cap heights, down to a
floor of 1.2 — below that one line's capitals run into the line above whatever
the glyphs are.

The letters come from [stroke_font.py](stroke_font.py), a single-stroke font
built into the repo rather than a font file — every line lands exactly one
stroke wide, which is what a nozzle wants, and there is no font dependency to
install. It covers `A–Z`, `0–9`, common punctuation and the Polish letters
`Ą Ć Ę Ł Ń Ó Ś Ź Ż`; text is raised as capitals, and any character it has no
glyph for stops the build rather than being dropped silently.

An accented word is taller than its cap height, since the marks sit clear above
the cap and below the baseline. A self-sizing label measures what it actually
drew, so it shrinks to fit rather than running its accents into the wall.

Two things are refused rather than printed badly: a label on a compartment that
is split into sub-compartments — it has no floor of its own, so label the
children instead — and a cap height under three times the stroke, which closes
the letters into a blob. A stated `size` that overruns the floor is refused too,
with the measurement it came to; leave `size` out and it fits itself instead.

Whatever sits in a labelled compartment rests on the letters, so it sits
`height` higher — 0.6 mm by default. That is nothing under a stack of cards, but
for anything that has to sit flat, cut the label in instead of raising it:

```jsonc
"coins": { "emboss": { "text": "COINS", "depth": 0.4 } }
```

`depth` is what asks for engraving, and sets how deep it goes — so the two
cannot disagree. State `height` or `depth`, never both, and a label that states
one overrides a section defaulting the other way. An engraved label has to leave
at least 0.4 mm of floor under it, about two layers, or the build stops rather
than printing a window.

Both directions print without supports: one adds to a floor that is already
there, the other takes from it, and neither overhangs.

### Box layout

The parts are only half the problem. The other half is whether they all go back
in the box, which is arithmetic done on the kitchen table and redone from
scratch every time a tray is resized. The `box` section states the arrangement
instead, and [check_box.py](check_box.py) works the rest out.

It is stated the way you would describe it out loud, in the same `[W, L, H]`
frame as every other size in the file:

| | |
| --- | --- |
| **W** | across the box. The arrangement's own entries follow each other along W |
| **L** | along the box |
| **H** | up the box |

```jsonc
"box": {
  "size": [317.0, 365.0, 147.0],   // inside the game box
  "clearance": 2.0,                // optional slack off each axis, in total
  "extras": {                      // what is in the box that no script prints
    "manuals": { "size": [300.0, 300.0, 60.0] }
  },
  "place": [                       // across W, in written order
    "base_a_standard",
    "personal_files",
    { "id": "markers", "turn": true }
  ]
}
```

An entry in `place` is an object id, and an id is anything the file defines: a
card well, a card box, a tray, or an `extras` entry for the things no script
here prints — boards, rulebooks, bags. Ids are flat across the whole file, a
name used twice is refused rather than one of the pair quietly winning, and each
object is placed exactly once. `{ "id": ..., "turn": true }` lays an object
across, swapping its W and its L, which is the only way something like a
27 × 221 mm marker tray fits anywhere.

Nothing states a position. An entry starts where the entry before it in the same
run ends — so a resized tray moves what is stacked on it, leaves the rest of the
box alone, and the check cannot fall out of date behind the parts.

#### Runs

A single list across W would only describe a very dull box. Any entry can be a
**run** instead of a single thing: `along` says which way it goes, `place` says
what is in it, and it takes the slot one object would have taken. Its contents
follow each other along its own axis from the corner it was handed, and start
together on the other two. It comes to as much as they do — or to its own
optional `size`, where you want to reserve more than its contents need.

Runs hold runs, so the box is described to whatever depth it actually has. Arnak
wants a thin tray against one wall, a pile of boards beside it topped by a board
laid over everything, and three trays end to end down the far side:

```jsonc
"place": [
  "replaced_components",
  { "along": "H", "place": [
      { "along": "W", "place": [
          { "along": "H", "place": ["player_boards", "setup"] },
          { "along": "L", "place": ["archeogical_sites_large", "guardians"] }
      ]},
      "game_board_manual"
  ]}
]
```

Read it outward from any tray and it says where that tray is: `setup` is on
`player_boards`, that stack is beside the site trays, and `game_board_manual`
lies over the whole of it. Because a run stacks only what is in it, a tall
narrow tray at one end of the box does not push up everything at the other end
— which is exactly what a fixed layer would have done.

#### Gaps

Every position comes from what was written before it, which leaves one thing
unsayable: something standing over an empty corner has nothing to push it clear
of that corner. In Arnak the `replaced_components` tray is 12 mm wide but only
116 long, so past it the box is free right up to the wall — and the boards that
lie over the whole box still have to start 12 mm in to clear its 66 mm height.

A `gap` is what to write there. It reserves that much space along the run
holding it, holds nothing, and is checked for nothing:

```jsonc
{ "along": "W", "place": [ { "gap": 12.0 }, "game_board_manual" ] }
```

Without it the only way to offset something was to find an object the right
width to put in front of it, which meant inventing a part that does not exist.

From all that every object gets an exact box, and the checks are statements
about those boxes. Three of them stop the run: something standing outside the
game box, two things in the same place, or something off the floor with nothing
at all under it. The rest are warnings, because they are judgement calls — a
tray only partly supported, one resting on air, or a part that was built and
then placed nowhere. It prints what the box has left over, and writes
`models/<game_id>/box/<game_id>_box_preview.stl` — one plain block per object
where the report says it sits, which the dev container opens in the editor.

What it will not do is arrange the box for you. It checks the arrangement you
wrote.

## Requirements

Python 3 and the packages in [requirements.txt](requirements.txt) — `trimesh`
with `manifold3d` for the booleans, plus its mesh and geometry helpers.

## Dev container

[.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) describes a
ready-to-run environment, so nothing has to be installed on the host. Open the
folder in VS Code and choose **Reopen in Container** (or use the `devcontainer`
CLI, or GitHub Codespaces).

It builds on the official `mcr.microsoft.com/devcontainers/python:3.14` image
and runs `pip install -r requirements.txt` on create, so the generators work
straight away. VS Code gets Ruff as the Python formatter, Pylance, and a 3D
preview extension for opening the exported STLs in the editor.

Dependency versions of the dev container features are pinned by digest in
`devcontainer-lock.json`; delete it to pick up newer releases on the next
rebuild.

## License

[MIT](LICENSE)
