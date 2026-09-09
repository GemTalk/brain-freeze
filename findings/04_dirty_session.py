"""Finding 4: a read-only session is not clean, so `refresh()` refuses.

    gemdb findings/04_dirty_session.py

Commits and aborts nothing that matters -- it defines one function, calls it,
and inspects the session. Safe to run at any time.

WHY THIS MATTERS

FR-4.4 says "a question asked before and after a change returns updated
results". It does not, without a deliberate act, and the obvious act does not
work.

A GemStone session sees the repository as of its last transaction boundary, so
another surface's commit is invisible until this session takes a new view. The
obvious `gemdb.refresh()` usually **refuses**, because Grail compiles a Python
function to a Smalltalk method the first time it is called and that
compilation is a repository write. A session can therefore be clean, call one
pure arithmetic function, and be dirty again with nothing of its own stored.

`gemdb.abort()` does take a new view, and is the wrong tool in a notebook: it
discards the session's uncommitted work, **including the functions defined in
earlier cells**. Anything you defined stops existing.

The recipe is `gemdb.commit()` then `gemdb.refresh()` -- keep the compiled
code, then take the new view.

(The same behaviour is finding 2 and rule 4 of
`GemDB_Code/docs/demo/brain-freeze/model.py (at c9c261a)`, found independently.)
"""

import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
TITLE = "Finding 4: a read-only session is not clean."


def pure_arithmetic(n):
    """Stores nothing, reads no record, touches no root."""
    return n * 2 + 1


def dirty_session():
    import gemdb

    print(TITLE)
    print("-" * 70)
    print()

    # Measured FIRST, before anything commits: this session has run a script,
    # and running it compiled it into the database.
    at_start = gemdb.needs_commit()
    print("  %-46s %s" % ("needs_commit() before doing anything", at_start))

    if at_start:
        print()
        print("  Nothing has been stored. The session is dirty because")
        print("  running this file compiled it into the database -- which is")
        print("  what every notebook cell does too.")

    print()
    try:
        gemdb.refresh()
        print("  %-46s %s" % ("refresh() from here", "allowed"))
        refused = False
    except Exception as error:
        refused = True
        print("  %-46s %s" % ("refresh() from here", "REFUSED"))
        print("      %s" % error)

    if refused:
        print()
        print("  That is the trap. In a notebook every cell you have run has")
        print("  already dirtied the session, so the cell that goes looking")
        print("  for another surface's changes is the one that fails.")

    print()
    print("  The recipe:")
    print()
    print("      gemdb.commit()     # keep this session's compiled code")
    print("      gemdb.refresh()    # then take the new view")
    print()
    gemdb.commit()
    gemdb.refresh()
    print("  %-46s %s" % ("after commit() + refresh()", gemdb.needs_commit()))
    print("  %-46s %s" % ("and pure_arithmetic still exists",
                          pure_arithmetic(20) == 41))

    # A second measurement, for the record: once committed, does calling a
    # function nothing has ever compiled dirty the session again? The
    # GemDB_Code demo's rule 4 says yes, measured on Grail 46c2a68.
    import random
    name = "never_called_%d" % random.randint(1, 10 ** 8)   # Grail: interval < 2**32
    namespace = {}
    exec(compile("def %s(n):\n    return n * 2 + 1\n" % name,
                 "<fresh>", "exec"), namespace)
    clean_before = gemdb.needs_commit()
    namespace[name](20)
    print()
    print("  %-46s %s -> %s" % ("first call of a never-compiled function",
                                clean_before, gemdb.needs_commit()))
    if gemdb.needs_commit() == clean_before:
        print("      did not dirty the session on this Grail; the GemDB_Code")
        print("      demo's rule 4 reports the opposite on 46c2a68.")
    else:
        print("      dirtied the session, as that demo's rule 4 describes.")

    print()
    print("  Do NOT use abort() for this. It also takes a new view, and it")
    print("  discards the definitions this session made -- in a notebook,")
    print("  the functions from your earlier cells stop existing.")
    gemdb.commit()
    return 0


if __name__ == "__main__":
    sys.exit(dirty_session())
