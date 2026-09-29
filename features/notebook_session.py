"""A notebook kernel, for the acceptance suite: one session that stays open.

    gemdb features/notebook_session.py DIR

Runs every code cell of brain-freeze.ipynb except the last -- the refresh
beat, which the scenario performs itself -- then waits for commands in
DIR/command and writes each answer to DIR/answer:

    count     print the policy count, the way cell 11 does, without refreshing
    refresh   gemdb.refresh()
    quit      stop

Driven by features/steps/tutorial_steps.py. Files rather than stdin because
this runs inside topaz.
"""

import contextlib
import io
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = sys.argv[1]

import gemdb                                   # noqa: E402


def answer(name, text):
    path = os.path.join(DIR, name)
    with open(path + ".tmp", "w") as handle:
        handle.write(text)
    os.rename(path + ".tmp", path)


def count():
    return "policies: %d\n" % len(gemdb.root["brainfreeze"])


with open(os.path.join(REPO, "brain-freeze.ipynb"), encoding="utf-8") as handle:
    cells = [c for c in json.load(handle)["cells"] if c["cell_type"] == "code"]

namespace = {"__name__": "__notebook__"}
printed = io.StringIO()
with contextlib.redirect_stdout(printed):
    for number, cell in enumerate(cells[:-1], 1):
        print("-- cell %d" % number)
        exec(compile("".join(cell["source"]), "<cell %d>" % number, "exec"), namespace)
answer("ready", printed.getvalue() + count())

while True:
    path = os.path.join(DIR, "command")
    if not os.path.exists(path):
        time.sleep(0.2)
        continue
    with open(path) as handle:
        command = handle.read().strip()
    os.remove(path)
    if command == "count":
        answer("answer", count())
    elif command == "refresh":
        try:
            gemdb.refresh()
            answer("answer", "refresh: ok\n")
        except Exception as refused:
            answer("answer", "refresh: refused -- %s: %s\n"
                   % (type(refused).__name__, refused))
    elif command == "quit":
        answer("answer", "bye\n")
        break
    else:
        answer("answer", "unknown command %r\n" % command)
