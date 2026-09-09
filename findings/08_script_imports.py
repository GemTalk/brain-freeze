"""Finding 8: what a script can import, and what the database remembers.

    gemdb findings/08_script_imports.py     # run it TWICE

Two halves. The first is about where `sys.path` points, and it is fixed on
current Grail -- with one wrinkle still worth knowing. The second is about the
database keeping a compiled copy of a module and serving it in preference to
the file on disk, and that one is live and cost the most time of anything in
this repo.

Run 1 measures the path, writes a throwaway PACKAGE, imports it, commits, and
edits it. Run 2 is a fresh session that imports the same package. Two runs
because a genuine re-import needs a genuine new session.

**THE COMMIT IS THE WHOLE MECHANISM, AND IT IS NOT A MISTAKE**

Without `gemdb.commit()` in run 1, run 2 reads the edited file quite happily.
The first draft of this script had no commit and concluded there was no
problem. Compiling a module is a repository write; COMMITTING it is what makes
the database keep the compiled copy and hand it to every later session.

Which puts two pieces of good advice in direct conflict. `findings/class-
identity/` establishes that you must commit after your imports, or instances
you write are stranded on a class the next session does not recognise. That
rule is right. This is its price: the same commit that stabilises your classes
freezes your code, and nothing tells you which version you are running.

`redeploy.py` in this repo is the way out, and it is not obvious -- deleting
the module from `sys.modules` makes it unimportable for the rest of the
session rather than fresh.

It writes `findings/tmp_neighbour/` and removes it at the end of run 2. It
never touches `gemdb.root` and never touches `brainfreeze/`.

WHY THE SECOND HALF MATTERS MORE THAN IT SOUNDS

`tests/test_app.py` was edited over and over with no effect, run after run,
while edits to top-level `app.py` in the same tree took effect immediately.
`run_db_tests.py` reads its test modules and `exec`s them rather than importing
them, for exactly this reason: a runner that silently tests the previous
version of the tests is worse than no runner.

The same thing at package scale ate an afternoon during the money work. The
database went on running a float `annual_premium` for an hour after the file on
disk had returned exact `Decimal`, and every test passed -- against last week's
rules. `redeploy.py` in this repo is the answer, and finding this out is what
it is for.
"""

import os
import shutil
import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
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
    """A PACKAGE, not a lone module, and that distinction is the finding.

    A top-level module picks up an edit on the next run. A module imported as
    part of a package does not: the database keeps what it compiled. Writing
    an `__init__.py` beside it is the whole difference.
    """
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
    print("    Grail issue #847 was that a script could not import the module")
    print("    beside it. That is fixed -- 8c8f503e, 2026-08-29 -- and the")
    print("    import below confirms it on your build.")
    print()
    print("    But note what sys.path[0] IS: a path RELATIVE to the working")
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

    # The commit is the whole experiment. Compiling a module is a repository
    # write; committing it is what makes the database keep the compiled copy
    # and hand it back to every later session. Without this line run 2 reads
    # the edited file quite happily, which is why the first version of this
    # script concluded there was no problem.
    #
    # It is the same instruction as the class-identity rule in
    # `findings/class-identity/`: commit after your imports. That rule keeps
    # class identity stable, and this is the price it charges.
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
        print("  The edit took, even for a package. Either your Grail differs")
        print("  from the one this was measured on, or the package was never")
        print("  deployed -- record which, because this repo measured the")
        print("  opposite and `redeploy.py` exists because of it.")
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
    print("  fresh. That residue is finding 2 in another costume.")
    return 0


def script_imports():
    print(TITLE)
    print("-" * 70)
    if os.path.exists(MARKER):
        return run_two()
    return run_one()


if __name__ == "__main__":
    sys.exit(script_imports())
