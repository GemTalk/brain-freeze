"""Finding 2: `__main__` is one namespace shared by every script the database
has ever run, and dispatch is by argument count.

    gemdb findings/02_main_namespace.py

Read-only apart from what running any script writes anyway.

WHY THIS MATTERS

`gemdb app.py` started failing with `name 'PREAMBLE' is not defined` -- a
global belonging to a completely different script in the same directory.

Two facts combine to produce that:

1. Every script runs as `__main__`, and `__main__` is compiled into the
   database and *kept*. A new script starts with the accumulated globals of
   every script this database has run, across sessions.

2. Grail dispatches by argument count, and default values do not
   disambiguate. A function declared `main(host="...", port=5000)` and called
   as `main()` is a zero-argument call, and can resolve to a *different*
   script's zero-argument `main`.

So `app.py`'s `if __name__ == "__main__": main()` reached the question
generator's `main()` and died inside it. Nothing about the failure pointed at
the cause.

The rule that falls out: **do not name a script's entry point `main`.** Give
it a name the file owns, so no two of them can be the same zero-argument
selector. Every script in this repo does: `serve()`, `generate()`,
`refresh()`, `seed_database()`, `check_shim()`, `main_namespace()`,
`class_identity()`, `dirty_session()`, `module_monkeypatch()`.
"""

import sys

#: Not `__doc__` -- see the body of this very finding: `__main__` is shared,
#: and `__doc__` in it is whatever the last script left there.
TITLE = """Finding 2: `__main__` is shared by every script, and dispatch is\nby argument count."""


def main_namespace():
    # `TITLE` belongs here too. This file defines it at import time, before
    # the function runs, so it is already in `globals()` and would otherwise
    # be reported as somebody else's -- in the one script whose subject is
    # knowing whose name is whose. Every findings script defines a TITLE, so
    # a copy really is inherited as well; both are true and neither is worth
    # the confusion of listing.
    mine = {"main_namespace", "inherited", "sys", "TITLE"}
    inherited = sorted(n for n in globals()
                       if not n.startswith("__") and n not in mine)

    print(TITLE)
    print("-" * 70)
    print()
    print("  __name__ is: %s" % __name__)
    print()
    if not inherited:
        print("  This __main__ carries no globals from other scripts.")
        print("  Either this is a fresh database, or nothing else has run in")
        print("  it. Run `gemdb seed.py` and then this script again.")
    else:
        print("  %d names are here before this script defines anything:" %
              len(inherited))
        print()
        width = max(len(n) for n in inherited)
        for name in inherited:
            value = globals()[name]
            kind = type(value).__name__
            print("    %-*s  %s" % (width, name, kind))
        print()
        print("  None of those were written by this file, and they persist")
        print("  in the database between sessions. Some belong to this repo")
        print("  -- seed.py, app.py, make_mcp_questions.py, the other")
        print("  findings. Others are whatever anyone ran here once and")
        print("  threw away, which is the part worth noticing: a throwaway")
        print("  script leaves its names behind for good.")

    print()
    print("  The dispatch half:")
    print()
    stray = callable(globals().get("main"))
    print("    a zero-argument `main` inherited from elsewhere:",
          "yes" if stray else "no")
    print()
    if stray:
        print("  Something this database ran left a `main` behind, and any")
        print("  `main()` call from any later script now lands in it.")
    else:
        print("  \"no\" is this rule being kept, not the hazard being absent.")
        print("  No script in this repo names its entry point `main`, so")
        print("  there is nothing here for a stray `main()` to resolve to.")
        print("  Run a script that defines one and this line says yes.")
    print()
    print("  A call site with no arguments resolves to a zero-argument")
    print("  definition. Defaults are not part of the selector, so")
    print("  `def main(host='x', port=1)` does NOT satisfy a `main()` call")
    print("  in preference to somebody else's `def main()`.")
    return 0


if __name__ == "__main__":
    sys.exit(main_namespace())
