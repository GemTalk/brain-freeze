"""A path helper works until something commits, and then silently stops.

    gemdb findings/09_imported_module_sys.py        # run it TWICE

WHAT IT COSTS

`gemdb tools/seed.py` puts the SCRIPT's directory on `sys.path` -- `tools/` --
not the working directory and not the repository. So every entry point that
lives in a subdirectory has to say where the repository is before it can
import `brainfreeze` at all:

    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if REPO not in sys.path:
        sys.path.insert(0, REPO)

Nine scripts, three lines each, and the obvious tidy-up is a module beside
them that does it once and is imported for the side effect. That was written,
and it worked: the seeder ran, the redeploy ran.

The redeploy committed. Every run after it failed with

    No module named 'brainfreeze'

from scripts whose first statement was the thing that was supposed to prevent
exactly that.

WHAT IS ACTUALLY HAPPENING

A module imported during a session that commits is kept by the database. In
every later session the helper still runs, and `REPO` is still right, and the
path it inserts goes onto a `sys` that is **not the caller's** -- the two
modules no longer share one `sys` object. Nothing raises. The insert simply
lands somewhere nobody is looking.

This is finding 8 with a sharper edge. Finding 8 is about a committed module
being served stale; this is the same machinery producing a module that is not
stale at all -- its source is re-read, its constants are correct -- and is
still not the module you wrote.

WHAT TO DO INSTEAD

Put the three lines in each entry point. The duplication is cheaper than a
helper that silently does not help, and it is why `web/app.py` and every
script in `tools/` repeats them.

THE ASYMMETRY IS WORTH KNOWING

A path inserted by the RUNNING SCRIPT is visible to everything it goes on to
import, before and after a commit alike. That is why `tools/run_db_tests.py`
can put `web/` on the path and then execute test modules that `import app`.
Only the other direction is lost.

NOTE: each cycle leaves one throwaway module compiled in the database, the way
any script that imports something and commits does. That is the finding -- and
it is why each run uses a module name this database has not seen before, since
re-using one would make the script work exactly once.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

#: Which module this cycle is using, so run 2 imports the one run 1 made.
MARKER_FILE = os.path.join(HERE, ".finding09_ran")

MARKER = "/finding-09-was-here"

HELPER_SOURCE = '''"""Written by finding 9. A stand-in for any `_paths.py`."""
import sys

MARKER = %r
if MARKER not in sys.path:
    sys.path.insert(0, MARKER)

WHAT_I_SEE = list(sys.path)
MY_SYS = sys
''' % MARKER


def helper_path(name):
    return os.path.join(HERE, "%s.py" % name)


def fresh_name():
    """A module name this database has never compiled.

    Re-using one name would make the script work exactly once per database:
    after the first cycle the committed copy is what gets served, so run 1
    would start in the state run 2 exists to show. The clock is enough --
    Grail has no `random.Random`.
    """
    return "_finding09_helper_%d" % time.time()


def report(helper):
    print()
    print("  the helper inserted %r into sys.path." % MARKER)
    print()
    print("    it sees it on its own path : %s" % (MARKER in helper.WHAT_I_SEE))
    print("    the caller sees it         : %s" % (MARKER in sys.path))
    print("    the two share one `sys`    : %s" % (helper.MY_SYS is sys))
    print()
    return MARKER in sys.path


def main():
    import gemdb

    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    first_run = not os.path.exists(MARKER_FILE)
    if first_run:
        name = fresh_name()
        with open(helper_path(name), "w") as handle:
            handle.write(HELPER_SOURCE)
    else:
        with open(MARKER_FILE) as handle:
            name = handle.read().strip()
        if not os.path.exists(helper_path(name)):
            print("  %s.py is gone -- starting the cycle over." % name)
            os.remove(MARKER_FILE)
            return 1

    helper = __import__(name)
    reached_the_caller = report(helper)

    if first_run:
        if not reached_the_caller:
            print("  Unexpected: it did not work even before a commit, on a")
            print("  module this database has never seen. Investigate that")
            print("  before reading anything else here.")
            os.remove(helper_path(name))
            return 1
        print("  Before any commit, the helper does what it was written to do.")
        gemdb.commit()
        with open(MARKER_FILE, "w") as handle:
            handle.write(name)
        print("  Committed, exactly as `gemdb tools/redeploy.py` does.")
        print()
        print("  Run this again.")
        return 0

    if reached_the_caller:
        print("  This runtime propagates it even after a commit, so a shared")
        print("  path helper would be safe here. It is not safe on the build")
        print("  this was measured on.")
    else:
        print("  LOST. Same helper, same source, same constants -- and the")
        print("  caller's path is unchanged, so a script leaning on it fails")
        print("  with `No module named 'brainfreeze'`: a message that names")
        print("  the package rather than the mechanism.")
        print()
        print("  Every entry point in `tools/` and `web/` therefore repeats")
        print("  the three lines itself.")

    for junk in (helper_path(name), MARKER_FILE):
        if os.path.exists(junk):
            os.remove(junk)
    print()
    print("  cleaned up the files; the compiled module stays in the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
