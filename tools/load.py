"""Load what is on disk into the database, so the running app serves it.

    gemdb tools/load.py

Step 3 of the tutorial. Edit the model, the form or a page, run this, and
reload the browser: the app is still running, and its next request runs the
code you loaded.

WHAT IT DOES

Imports every module in `brainfreeze/` and `web/` in a fresh session, then
commits. A fresh session's import compares each file with what the database
compiled from it, and rebuilds the ones that changed -- in place, so a class
keeps its identity and every object already committed under it reads the new
definition. The commit is what makes that visible to other sessions, and the
app takes a fresh view before every request.

Imported as `import package.module`, never `from package import module`:
the second form hands back the committed copy without checking the file
(GemTalk/Grail#1223, #86).

WHAT IT DOES NOT DO

It does not reshape stored data. Adding a field with a class-level default
needs nothing more; changing what a field means needs `tools/seed.py` too.

It does not restart the app, and a change to `web/app.py` itself, or a new
route, needs one: the app is built once, when it starts. See web/routes.py.
"""

import importlib
import os
import sys

#: Both roots, the way the app sees them: the repository for `brainfreeze`,
#: and `web/` for the app's modules, which import each other as siblings.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(REPO, "web")
for path in (WEB, REPO):
    if path not in sys.path:
        sys.path.insert(0, path)

import gemdb                                    # noqa: E402


def modules():
    package = sorted(name[:-3] for name in os.listdir(os.path.join(REPO, "brainfreeze"))
                     if name.endswith(".py") and name != "__init__.py")
    # app.py is the entry point, and importing it would start nothing but
    # would not be what the app runs either; everything it serves is below.
    web = sorted(name[:-3] for name in os.listdir(WEB)
                 if name.endswith(".py") and name != "app.py")
    return ["brainfreeze"] + ["brainfreeze.%s" % n for n in package] + web


def load():
    for name in modules():
        importlib.import_module(name)
    try:
        changed = gemdb._pending_imports()
    except Exception:
        changed = []
    gemdb.commit()
    if changed:
        print("Loaded %s. Committed." % ", ".join(sorted(changed)))
    else:
        print("Nothing had changed. Committed.")
    print("Reload the page: the running app serves what you loaded.")


if __name__ == "__main__":
    load()
