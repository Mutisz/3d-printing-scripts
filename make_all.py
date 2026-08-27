"""
Build every part for one game, then check they all fit in the box.

Each script runs in turn against games/<game_id>.json and prints its own
report -- this runner adds nothing of its own. One whose section is missing
from the file exits clean with a note, since a game with no trays is an
ordinary game and not a failure. Anything else is a real failure, and it
stops the run then and there: the scripts that would have followed are not
started, and this exits with the code the failing one gave.

The fit check comes last, so a layout that does not hold still leaves you
the STLs it was complaining about, and the last thing printed is where
everything goes.

Run as: python3 make_all.py <game_id>
"""

import os
import subprocess
import sys

from gameconfig import load_game, parse_game_id

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = (
    "make_card_holder.py",
    "make_card_box.py",
    "make_resource_tray.py",
    "check_box.py",  # last: it builds nothing, and reports on what the rest did
)

# games/ and models/ are resolved relative to the working directory, so sit in
# the repo root and this runner works no matter where it was invoked from.
os.chdir(ROOT)

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
load_game(GAME_ID)  # fail once here on a bad id or unreadable version

for script in SCRIPTS:
    code = subprocess.run([sys.executable, script, GAME_ID]).returncode
    if code:  # it has already said why, so add nothing and go no further
        raise SystemExit(code)
