"""Finding 1: a database can be installed without the regex engine.

    gemdb findings/01_shim_missing.py

Read-only. Diagnoses, changes nothing.

WHY THIS MATTERS

An extent installed without the CPython shim starts, runs Python, seeds a
900-policy book and passes every test in this repo -- and then cannot import
`re`. Werkzeug's routing, Jinja2's lexer and all header parsing need it, so
Flask, Django and every other web framework fail together, with an error
message that names `_sre` and explains nothing.

`install.gs` records the shim path only when `SHIM_LIB_PATH` is non-empty, and
`install-grail.sh` blanks that variable when the library is not present at the
moment it looks -- then installs anyway, with a warning to a log. Nothing
later says the database is in this state.

Not documented anywhere in GemDB_Code as of 2026-09-08.
"""

import os
import sys

SHIM = "src/c/shim/libcpython_ua"

#: Not `__doc__`. Under Grail `__main__` is a namespace shared by every script
#: the database has run (see finding 2), and `__doc__` there is whatever was
#: left in it -- this script printed `object`'s docstring the first time.
TITLE = """Finding 1: can this database run a web framework at all?"""


def check(label, thunk):
    try:
        return True, "%-34s %s" % (label, thunk())
    except Exception as error:
        return False, "%-34s %s: %s" % (label, type(error).__name__, error)


def main():
    print(TITLE)
    print("-" * 70)

    results = []
    for label, thunk in (
        ("import re", _try_re),
        ("import flask", _try("flask")),
        ("import jinja2", _try("jinja2")),
        ("import werkzeug", _try("werkzeug")),
    ):
        ok, line = check(label, thunk)
        results.append(ok)
        print("  " + line)

    grail_dir = os.environ.get("GRAIL_DIR", "")
    print()
    print("  %-34s %s" % ("GRAIL_DIR", grail_dir or "(not set)"))
    print("  %-34s %s" % ("SHIM_LIB_PATH", os.environ.get("SHIM_LIB_PATH")
                          or "(not set)"))
    if grail_dir:
        for suffix in (".dylib", ".so"):
            path = os.path.join(grail_dir, SHIM + suffix)
            if os.path.exists(path):
                print("  %-34s %s" % ("shim library on disk", path))
                break
        else:
            print("  %-34s %s" % ("shim library on disk", "NOT FOUND"))

    print()
    if all(results):
        print("  VERDICT: this database can run a web framework.")
        return 0

    print("  VERDICT: this database CANNOT run a web framework.")
    print()
    print("  The library is almost certainly on disk; what is missing is the")
    print("  path recorded in the extent. Ask the database directly:")
    print()
    print("      topaz> CPythonShim libraryPath")
    print("      ERROR 2318 ... reason:halt,")
    print("             CPythonShim library path not configured.")
    print()
    print("  The fix is one assignment and a commit, NOT a reinstall --")
    print("  install.gs only ever records the path, because the shim's")
    print("  built-ins resolve lazily per gem. A full reinstall would")
    print("  recreate the Python runtime classes with new identity and")
    print("  orphan everything already committed.")
    print()
    print("      CPythonShim libraryPath: '<GRAIL_DIR>%s.dylib'." % SHIM)
    print("      System commit.")
    return 1


def _try_re():
    import re
    return "ok -- matched %r" % re.match(r"a+", "aaa").group()


def _try(name):
    def thunk():
        __import__(name)
        return "ok"
    return thunk


if __name__ == "__main__":
    sys.exit(main())
