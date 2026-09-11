"""Finding 5: you cannot monkeypatch a module inside the database.

    gemdb findings/05_module_monkeypatch.py

Rebinding an attribute on an imported module -- the ordinary way to spy on a
function in a test -- leaves the session in a dirty state that `commit()` does
**not** clear. Every later `gemdb.refresh()` then raises
`PendingChangesError`, so the instrumentation destroys what it was measuring.

This script restores what it patches and commits on the way out. It writes
nothing to `gemdb.root`.

WHY THIS MATTERS

It cost a real test. The web app was fixed to `commit()` then
`refresh()` before each request, and the natural test wraps both calls to
record the order:

    for name in ("commit", "refresh", "abort"):
        setattr(gemdb, name, recorded(name))

Every such test fails, and it fails *inside the code under test* rather than
at an assertion, which reads like the fix is broken. It is not.

Note what is NOT the cause. Defining a closure and calling it is fine, and so
is wrapping a bound function in a local name. Arm 1 below shows the recipe
working through freshly compiled wrappers held in ordinary variables. The
difference is assigning onto the **module object**, which Grail compiles into
the database and therefore treats as persistent -- and a function object is
not something it can write there.

WHAT TO DO INSTEAD

Introspect something that is not a persistent module. `tests/test_refresh.py`
reads `app.py`'s syntax tree under plain CPython to pin the call order, and
`tests/test_app.py` asks Flask for its own `before_request_funcs`. Both answer
the same question without touching `gemdb`.

For the product this is worth a clear error. "refresh() would discard
uncommitted changes" is true and points nowhere near a `setattr` three lines
earlier.
"""

import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
TITLE = "Finding 5: monkeypatching a module dirties the session permanently."


def report(label, action):
    try:
        action()
        print("    %-38s ok" % label)
        return True
    except Exception as error:
        print("    %-38s %s" % (label, type(error).__name__))
        print("      %s" % error)
        return False


def module_monkeypatch():
    import gemdb
    print(TITLE)
    print("-" * 70)

    def wrap(real, seen):
        def wrapper(*args, **kwargs):
            seen.append(real)
            return real(*args, **kwargs)
        return wrapper

    seen = []
    print("\n  ARM 1 -- wrappers in ordinary variables (not on the module)")
    commit = wrap(gemdb.commit, seen)
    refresh = wrap(gemdb.refresh, seen)
    report("commit(); refresh()", lambda: (commit(), refresh()))

    print("\n  ARM 2 -- the same wrappers assigned ONTO the module")
    original = {"commit": gemdb.commit, "refresh": gemdb.refresh}
    try:
        gemdb.commit = wrap(original["commit"], seen)
        gemdb.refresh = wrap(original["refresh"], seen)
        clean = report("commit(); refresh()",
                       lambda: (gemdb.commit(), gemdb.refresh()))

        print("\n  ARM 3 -- does a second commit rescue it?")
        report("commit(); commit(); refresh()",
               lambda: (gemdb.commit(), gemdb.commit(), gemdb.refresh()))
    finally:
        for name, real in original.items():
            setattr(gemdb, name, real)
        gemdb.commit()

    print("\n  Restored gemdb.commit and gemdb.refresh, and committed.")
    if not clean:
        print("\n  A module is persistent here, and a function object is not")
        print("  something Grail can write into it. The session stays dirty,")
        print("  commit does not clear it, and refresh refuses from then on.")
    else:
        print("\n  Arm 2 succeeded on your Grail -- that is the interesting")
        print("  result. Note your version and say so.")
    return 0


if __name__ == "__main__":
    sys.exit(module_monkeypatch())
