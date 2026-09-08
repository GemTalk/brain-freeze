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

The rule that falls out: **do not name a script's entry point `main`.** This
repo's are `serve()` and `generate()`.
"""

import sys

#: Not `__doc__` -- see the body of this very finding: `__main__` is shared,
#: and `__doc__` in it is whatever the last script left there.
TITLE = """Finding 2: `__main__` is shared by every script, and dispatch is\nby argument count."""


def report():
    mine = {"report", "inherited", "sys"}
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
        print("  None of those were written by this file. They belong to")
        print("  seed.py, app.py, run_app_tests.py and make_mcp_questions.py,")
        print("  and they persist in the database between sessions.")

    print()
    print("  The dispatch half, demonstrated:")
    print()
    print("    a zero-argument `main` inherited from elsewhere:",
          "yes" if callable(globals().get("main")) else "no (none inherited)")
    print()
    print("  A call site with no arguments resolves to a zero-argument")
    print("  definition. Defaults are not part of the selector, so")
    print("  `def main(host='x', port=1)` does NOT satisfy a `main()` call")
    print("  in preference to somebody else's `def main()`.")
    return 0


if __name__ == "__main__":
    sys.exit(report())
