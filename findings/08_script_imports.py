"""Finding 8: what a script can import, and what the database keeps.

    gemdb findings/08_script_imports.py     # run it TWICE

Two halves. The first shows where `sys.path` points: a script can import the
module beside it (Grail#847, fixed), but `sys.path[0]` is relative to the
working directory, so a script that changes directory loses its neighbours.

The second is live (GemTalk/Grail#1223): once a package module has been
compiled and committed, `from package import module` in a later session
returns the committed copy without checking the file on disk, so an edit
does not take. `import package.module` does check, which is why
`tools/load.py` imports that way.

Run 1 measures the path, writes a throwaway package, imports it, commits, and
edits it. Run 2 is a fresh session that imports the same package. Two runs
because a genuine re-import needs a genuine new session. The commit in run 1
is the mechanism: without it, run 2 reads the edited file.

It writes `findings/tmp_neighbour/` and removes it at the end of run 2. It
never touches `gemdb.root` and never touches `brainfreeze/`.
"""

import os
import shutil
import sys

#: Not `__doc__`: older Grail builds shared `__main__` between scripts.
TITLE = "Finding 8: sys.path, and modules the database will not let go of."

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "tmp_neighbour")
MARKER = os.path.join(PKG, ".run1")

BEFORE = '''"""A throwaway module, so this finding touches nothing real."""

WHAT_THE_FILE_SAYS = "written by run 1"
'''

AFTER = '''"""A throwaway module, so this finding touches nothing real."""

WHAT_THE_FILE_SAYS = "EDITED between run 1 and run 2"
'''


def write_module(text):
    """A PACKAGE, not a lone module: a top-level module picks up an edit on
    the next run, and a module imported from a package does not."""
    if not os.path.isdir(PKG):
        os.makedirs(PKG)
    with open(os.path.join(PKG, "__init__.py"), "w") as handle:
        handle.write("")
    with open(os.path.join(PKG, "neighbour.py"), "w") as handle:
        handle.write(text)


def show_the_path():
    print("\n  WHERE A SCRIPT LOOKS FOR ITS NEIGHBOURS\n")
    print("    %-26s %s" % ("__file__", __file__))
    print("    %-26s %s" % ("the script's directory", HERE))
    print("    %-26s %s" % ("os.getcwd()", os.getcwd()))
    first = sys.path[0] if sys.path else "(empty)"
    print("    %-26s %r" % ("sys.path[0]", first))
    print("    %-26s %s" % ("...is it absolute?", os.path.isabs(first)))
    print()
    print("    Note what sys.path[0] IS: a path RELATIVE to the working")
    print("    directory, where CPython puts an absolute one. It resolves")
    print("    only while the process stays where it started. Anything that")
    print("    changes directory -- and a test runner reasonably might --")
    print("    silently takes the script's own neighbours off the path.")


def try_the_neighbour_import():
    print("\n  IMPORTING THE MODULE SITTING NEXT TO THIS ONE\n")
    added = False
    if HERE not in sys.path:
        sys.path.insert(0, HERE)          # so `tmp_neighbour` is a package here
        added = True
    try:
        from tmp_neighbour import neighbour
        print("    from tmp_neighbour import neighbour     ok")
        print("    it says                                 %r"
              % neighbour.WHAT_THE_FILE_SAYS)
        return neighbour.WHAT_THE_FILE_SAYS
    except ImportError as error:
        print("    from tmp_neighbour import neighbour     ImportError")
        print("      %s" % str(error)[:60])
        return None
    finally:
        if added:
            print("    (%r was put on sys.path by hand)" % HERE)


def run_one():
    import gemdb

    print("  RUN 1 -- measure the path, write the module, import it, COMMIT")
    show_the_path()
    write_module(BEFORE)
    said = try_the_neighbour_import()

    # The commit is the experiment: it is what makes the database keep the
    # compiled copy and hand it to later sessions. Without it, run 2 reads
    # the edited file.
    gemdb.commit()
    print("\n    committed -- the compiled module is now the database's")

    write_module(AFTER)
    with open(MARKER, "w") as handle:
        handle.write(said or "")

    print("\n  The file on disk now says %r." % "EDITED between run 1 and run 2")
    print("  Run this again -- a NEW session, importing the edited file:\n")
    print("      gemdb findings/08_script_imports.py")
    return 0


def run_two():
    print("  RUN 2 -- a fresh session, importing the file run 1 edited")
    show_the_path()
    said = try_the_neighbour_import()

    with open(MARKER) as handle:
        run1_said = handle.read()

    print("\n  WHAT THE DATABASE REMEMBERED\n")
    print("    run 1 read                  %r" % run1_said)
    print("    the file now says           %r" % "EDITED between run 1 and run 2")
    print("    run 2 read                  %r" % said)
    print()
    if said == "EDITED between run 1 and run 2":
        print("  The edit took. If this Grail has fixed Grail#1223, this finding")
        print("  can go; `tools/load.py` avoids this import form either way.")
    elif said == run1_said:
        print("  REPRODUCED. A new session, a new process, an edited file on")
        print("  disk -- and the database served what it compiled last time.")
        print("  Nothing in that sequence tells you the code you are running")
        print("  is not the code you are reading.")
    else:
        print("  Neither: run 2 read something else again. Record what your")
        print("  Grail did, because it matches neither measurement.")

    shutil.rmtree(PKG, ignore_errors=True)
    print("\n  Cleaned up: findings/tmp_neighbour/ removed from disk.")
    print("  Not from the database. A compiled module stays, and there is no")
    print("  supported way to take it out -- deleting it from `sys.modules`")
    print("  makes it unimportable for the rest of the session rather than")
    print("  fresh.")
    return 0


def script_imports():
    print(TITLE)
    print("-" * 70)
    if os.path.exists(MARKER):
        return run_two()
    return run_one()


if __name__ == "__main__":
    sys.exit(script_imports())
