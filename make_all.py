"""
Build every part for one game: card holders, card boxes, then resource trays.

Each generator runs in turn against games/<game_id>.json and prints its own
report -- this runner adds nothing of its own. A generator whose section is
missing from the file exits clean with a note, since a game with no trays is
an ordinary game and not a failure. Anything else is a real failure, and it
stops the run then and there: the generators that would have followed are
not started, and this exits with the code the failing one gave.

Run as: python3 make_all.py <game_id>
"""

import os
import subprocess
import sys

from gameconfig import load_game, parse_game_id

ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATORS = ("make_card_holder.py", "make_card_box.py", "make_resource_tray.py")

# games/ and models/ are resolved relative to the working directory, so sit in
# the repo root and this runner works no matter where it was invoked from.
os.chdir(ROOT)

GAME_ID = parse_game_id(__doc__.strip().splitlines()[0])
load_game(GAME_ID)  # fail once here on a bad id or unreadable version

for script in GENERATORS:
    code = subprocess.run([sys.executable, script, GAME_ID]).returncode
    if code:  # it has already said why, so add nothing and go no further
        raise SystemExit(code)
