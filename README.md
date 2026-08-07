# 3d-printing-scripts

Parametric generators for 3D-printable board game inserts. Each script builds
its meshes with [trimesh](https://trimesh.org) boolean operations and exports
STLs ready to slice.

## Scripts

| Script | Makes |
| --- | --- |
| [make_all.py](make_all.py) | Both generators below, in turn, for one game |
| [make_card_holder.py](make_card_holder.py) | Top-loaded card trays — solid floor and end walls, long sides open between four corner posts so cards stay reachable but cannot slide out. Plus matching card separators, if the game asks for them |
| [make_resource_tray.py](make_resource_tray.py) | Open-top trays split into a row of compartments, with exact outside dimensions and optional raised floors for small pieces |
| [gameconfig.py](gameconfig.py) | Not a generator — loads the per-game parameter files and documents their schema |

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
                                 "pack_axis": "W", "pack_count": 2,
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
