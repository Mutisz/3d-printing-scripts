# 3d-printing-scripts

Parametric generators for 3D-printable board game inserts. Each script builds
its meshes with [trimesh](https://trimesh.org) boolean operations and exports
STLs ready to slice.

## Scripts

| Script | Makes |
| --- | --- |
| [make_card_holder.py](make_card_holder.py) | Top-loaded card trays — solid floor and end walls, long sides open between four corner posts so cards stay reachable but cannot slide out |
| [make_resource_tray.py](make_resource_tray.py) | Open-top trays split into a row of compartments, with exact outside dimensions and optional raised floors for small pieces |

## Usage

Open the repo in the dev container (see below) and the dependencies are already
there. Otherwise, install them yourself:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run whichever generator you need:

```bash
python make_card_holder.py
python make_resource_tray.py
```

Each script prints its dimensions, mesh checks (watertight, body count, Euler
number) and an estimated filament weight, then writes STLs to
`./models/<GAME_ID>/`. That directory is git-ignored — the scripts are the
source of truth, the models are output.

## Configuring

There is no CLI. Every knob lives in the `# ---- Parameters ----` block at the
top of each script: edit it and re-run.

Set `GAME_ID` to name the output folder and file prefix, then describe what you
need in `VARIANTS` — one entry per part, keyed by name. The comments above
`VARIANTS` document each field. Both scripts validate their inputs and fail with
a message explaining the conflict rather than exporting a bad mesh.

Shared build settings are `T` (wall thickness) and `F` (floor thickness), both
1.0 mm by default.

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
