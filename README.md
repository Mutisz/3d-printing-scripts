# 3d-printing-scripts

Parametric generators for 3D-printable board game inserts. Each script builds
its meshes with [trimesh](https://trimesh.org) boolean operations and exports
STLs ready to slice.

## Scripts

| Script | Makes |
| --- | --- |
| [make_all.py](make_all.py) | Both generators below, in turn, for one game |
| [make_card_holder.py](make_card_holder.py) | Top-loaded card trays — solid floor and end walls, long sides open between four corner posts so cards stay reachable but cannot slide out. Plus matching card separators, if the game asks for them |
| [make_resource_tray.py](make_resource_tray.py) | Open-top trays split into a row of compartments, with exact outside dimensions, optional raised floors for small pieces, and walls that can be notched or opened out entirely |
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
python make_all.py cafe_baras           # everything for that game
python make_card_holder.py cafe_baras   # or just one generator
python make_resource_tray.py cafe_baras
```

Each generator prints its dimensions, mesh checks (watertight, body count, Euler
number) and an estimated filament weight, then writes STLs to its own folder
under `./models/<game_id>/`:

```
models/cafe_baras/
├── card_holders/   written by make_card_holder.py
└── trays/          written by make_resource_tray.py
```

`models/` is git-ignored — the parameter files are the source of truth, the
models are output.

Each generator **empties its own folder before it builds**, so what is in there
afterwards is exactly what that run produced. Rename a variant, or delete one,
and the STL it used to write goes with it rather than lingering to be printed by
mistake. Nothing else should be kept in those folders. The wipe happens even
when there is nothing to build, so removing a whole section from the parameter
file clears the parts it used to make.

`make_all.py` runs both generators and ends with a pass/fail summary and a
listing of everything under the game's output folder. A game that defines no
trays (or no card holders) is not an error: the generator with nothing to do
says so and exits clean.

## Configuring

Parameters live in one JSON file per game, `games/<game_id>.json`, holding both
the card holders and the trays for that game. Nothing is configured by editing
the scripts.

Each file declares the `schema_version` it was written against, and the loader
refuses a version it does not understand rather than misreading it. The schema
is documented in full in the [gameconfig.py](gameconfig.py) docstring — JSON has
no comments, so that is where the field-by-field reference lives.

Sketch:

```jsonc
{
  "schema_version": 3,
  "game": { "id": "cafe_baras", "name": "Cafe Baras" },
  "card_holders": {
    "wall": 1.0, "floor": 1.0, "card_thickness": 0.6,
    "sleeve": [67.0, 91.0], "clearance": 1.0,
    "separator": { "thickness": 1.0, "fit": 0.2, "tab_out": null },
    "variants": { "main_deck": { "size": [70.0, 94.0, 31.0], "corner": 10.0,
                                 "separators": 0 } }
  },
  "trays": {
    "wall": 1.0, "floor": 1.0,
    "variants": { "coins": { "size": [70.0, 94.0, 21.0], "split": "L",
                             "compartments": [ { "name": "1", "size": null },
                                               { "name": "5", "size": 30.0 } ] } }
  }
}
```

Either top-level section may be omitted. Both generators validate what they read
and fail with a message naming the conflict — and the offending key's path in
the file — rather than exporting a bad mesh.

### Outside dimensions, checked sleeves

Card holders are stated the way trays are: `size` is the outside `[W, L, H]`,
because that is the hard constraint when the thing has to drop into a box. The
cavity is whatever is left inside the walls and over the floor.

The sleeve sets no dimension. State one and the cavity that came out is checked
against it — the report says how much room is left over, and a cavity too small
for the sleeve plus `clearance` stops the build. `clearance` is that demanded
margin, in total across each axis, and defaults to 0.

```jsonc
"card_holders": {
  "sleeve": [67.0, 91.0], "clearance": 1.0,  // checked unless overridden
  "variants": {
    "main_deck":  { "size": [70.0, 94.0, 31.0], /* ... */ },
    "mini_cards": { "size": [48.0, 71.0, 21.0], "sleeve": [45.0, 68.0], /* ... */ }
  }
}
```

Both keys are optional. Drop them and nothing is checked; state a `sleeve` on
one variant only and that variant alone is. The escape check — is the side
opening shorter than a card? — needs a sleeve too, and says so when it has none.

### Separator tabs

A separator's tabs are not configured. Each one fills the side opening its
holder actually has — `L` less the two `corner` posts — minus the same `fit`
that shrinks the sheet, so the tab is as long as it can be, reaches through the
opening whatever the corner posts are set to, and cannot fall out of step with
them. `separator.tab_out` still sets how far it stands proud; `null` means flush
with the outer wall.

### Nested compartments

A tray compartment that carries `compartments` of its own is subdivided across
the *perpendicular* axis, so a row along `L` becomes columns along `W`. Nest as
deep as you like; the axis flips at every level, which is what turns nesting
into a grid. `depth` set on a parent becomes the default for everything under
it.

```jsonc
"compartments": [
  { "name": "cubes", "size": 40.0, "depth": 10.0, "compartments": [
      { "name": "red",   "size": null },   // three equal columns,
      { "name": "green", "size": null },   // each 10 mm deep
      { "name": "blue",  "size": null }
  ]},
  { "name": "coins", "size": null }        // full-depth, rest of the tray
]
```

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
`depth` all the way. The report says which kind each notch turned out to be.

Nothing overhangs — a notch only removes material from the rim down, leaving a
shorter wall — so trays still print without supports.

### Open sides

When a notch is not enough, `openings` takes the whole wall out instead — rim
to floor, over the wall's whole length bar a post left standing at each end.
That is the card holder's open side, in a tray: reach in from the side and lift
a stack straight out, while the posts keep it from sliding out on its own.

```jsonc
"compartments": [
  { "name": "event_tiles", "size": 46.0, "openings": [
      { "side": "L-", "corner": 12.0 },      // 12 mm post at each end
      { "side": "L+", "corner": 12.0 }
  ]},
  { "name": "pawns", "size": null, "openings": [
      { "side": "L+" }                       // corner defaulted
  ]}
]
```

`side` names the wall exactly as a notch does, dividers included. `corner` is
how much wall is kept at each end, and defaults to 20% of that wall — leaving
the middle 60% open, the same span a notch defaults to. Set it to `0` to take
the wall out entirely.

The card holder's `corner` is the same setting under another roof, and takes the
same default: state it, or get 20% of `L` at each end and the middle 60% of each
long side open.

`depth` defaults to the compartment's own depth, so the opening runs all the way
down to the floor; give it a smaller number to leave a lip standing. Either way
the cut only removes material downward from the rim, so this prints without
supports too.

Size the posts against what is inside: an opening shorter than the piece it
holds cannot let that piece out sideways. On a divider, a full-depth opening
merges the two compartments into one — the report says which walls turned out to
be dividers and which face outside.

### Embossed labels

Any compartment with a floor of its own can have a label raised off it, so a
tray comes out of the box knowing what goes where. A card holder takes the same
option on its variant, which puts the label on the cavity floor, under where the
cards sit — an empty holder still says which deck it belongs to.

```jsonc
"compartments": [
  { "name": "coins", "size": 40.0, "emboss": { "text": "COINS" } },
  { "name": "wood",  "size": null, "emboss": {
      "text": "WOOD", "size": 6.0, "height": 1.0, "along": "L" } }
]
```

`text` is all that is required. The label sizes itself to the compartment — up
to a 10 mm cap, since a label is a label — and turns to run along whichever axis
has more room, so a tray full of them needs no numbers typed per compartment.

| key | default |
| --- | --- |
| `size` | cap height that fits the compartment, capped at 10 mm |
| `stroke` | 14% of the cap height, never finer than 0.8 mm |
| `height` | 0.6 mm standing off the floor |
| `along` | `"W"` or `"L"`, whichever way the compartment is longer |

```jsonc
"card_holders": {
  "variants": {
    "main_deck": { "size": [70.0, 94.0, 31.0], "emboss": { "text": "MAIN DECK" } }
  }
}
```

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
it is worth dropping for anything that has to sit flat.

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
