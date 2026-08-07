"""
Build every part for one game: card holders, then resource trays.

Each generator runs in turn against games/<game_id>.json and streams its own
report. A generator whose section is missing from the file exits clean with a
note -- a game with no trays is an ordinary game, not a failure -- so only a
real error shows up as FAIL in the summary.

Run as: python3 make_all.py <game_id>
"""

import glob
import os
import subprocess
import sys

from gameconfig import MODELS_DIR, load_game, parse_game_id

ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATORS = ("make_card_holder.py", "make_resource_tray.py")

# games/ and models/ are resolved relative to the working directory, so sit in
# the repo root and this runner works no matter where it was invoked from.
os.chdir(ROOT)

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
CFG = load_game(GAME_ID)  # fail once here on a bad id or unreadable version

results = []
for script in GENERATORS:
    print()
    print("#" * 66)
    print(f"# {script} {GAME_ID}")
    # Flush, or our buffered header lands after the child's unbuffered output
    # whenever stdout is a pipe rather than a terminal.
    print("#" * 66, flush=True)
    results.append(
        (script, subprocess.run([sys.executable, script, GAME_ID]).returncode)
    )

print()
print("=" * 66)
print(f"Build summary -- {CFG['game']['name']}")
print("=" * 66)
for script, code in results:
    status = "ok" if code == 0 else f"FAIL (exit {code})"
    print(f"  {status:<16}{script}")

# One folder per generator under the game, each emptied by the generator that
# owns it, so list the tree rather than one flat directory.
game_dir = os.path.join(ROOT, MODELS_DIR, GAME_ID)
stls = sorted(glob.glob(os.path.join(game_dir, "**", "*.stl"), recursive=True))
print(f"  {len(stls)} STL(s) in {MODELS_DIR}/{GAME_ID}/")
for path in stls:
    rel = os.path.relpath(path, game_dir)
    print(f"    {rel:<58}{os.path.getsize(path) / 1024:>7.0f} KB")

raise SystemExit(1 if any(code for _, code in results) else 0)
