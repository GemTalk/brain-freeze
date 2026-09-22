"""Finding 10: calling a function another session has called can kill a
running app, permanently, and the reason never reaches a log.

    gemdb web/app.py                            # terminal 1, leave it up
    gemdb findings/10_compiled_code_conflict.py # terminal 2

This script is the second session. It needs the app running, and **it will
stop the app from answering** -- that is what it demonstrates. Nothing in the
book is written or changed; restart the app and everything is as it was.

WHY THIS MATTERS

`web/app.py` takes a new view before every request, and `take_new_view()`
commits first because `refresh()` refuses while a session holds uncommitted
work -- and it always does, because Grail compiles Python into the database
and rendering is therefore a repository write (finding 4).

That commit is the exposure. Grail compiles a function into the database
**when it is called**, not when its module is imported. So two sessions that
call the same function each write the same object. If the other session
commits first, the app's next `take_new_view()` is a Write-Write conflict.

The app cannot recover by aborting: `gemdb.abort()` would discard this
session's uncommitted work, which includes the app's own compiled handlers --
the server would throw away the code it is running (finding 2's cousin). So
the uncommitted work stays, and **every subsequent request re-attempts the
same commit and fails the same way.** The server is not slow and it is not
returning errors. It is dead, and it stays dead.

Then finding 7 removes the evidence: Flask reports the exception by calling
`Logger.error(..., exc_info=True)`, Grail's `logging` does not accept
`exc_info`, and the `TypeError` from the reporting call replaces the
`ConflictError` that caused it.

WHAT IS AND IS NOT ENOUGH (measured, four ways)

  another session defines a function and commits        -> app survives
  another session imports the module and commits        -> app survives
  another session CALLS a function the app never called -> app survives
  another session CALLS a function the app HAS called   -> app is dead

The last line is the finding. It is not "another session committed"; it is
"both sessions compiled the same callable".

WHERE IT BITES

The acceptance suite. `features/every_surface_agrees.feature` runs the
notebook inside the database to check it answers what the JSON surface
answers. The notebook calls `brainfreeze.analysis.book_summary`, and so does
`/api/stats`. Whichever the suite drove first, the app dies on the next
request, and every feature after it fails with an empty response.
"""

import os
import subprocess
import sys

import gemdb

#: Not `__doc__` -- `__main__` is shared between scripts; see finding 2.
TITLE = ("Finding 10: two sessions compiling the same callable, and the app "
         "that never answers again.")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:5000"


def _status(path):
    """The app's HTTP status for `path`, or None if it did not answer.

    `curl` rather than urllib: this runs inside the database, and shelling out
    is measured to work here while an HTTP client in Grail is one more thing
    that could be the reason the probe fails.
    """
    finished = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "--max-time", "120", BASE + path],
        capture_output=True, text=True)
    code = finished.stdout.strip()
    return None if code in ("", "000") else code


def compiled_code_conflict():
    print(TITLE)
    print("-" * 70)
    print()

    if REPO not in sys.path:
        sys.path.insert(0, REPO)

    print("  1. Is the app up, and has it compiled `book_summary`?")
    print("     Asking /api/stats, which calls it.")
    before = _status("/api/stats")
    if before is None:
        print()
        print("     The app did not answer. Start it first:")
        print("         gemdb web/app.py")
        print("     and run this again.")
        return
    print("     /api/stats -> %s.  The app has now compiled it." % before)
    print()

    print("  2. This session calls the same function, and commits.")
    from brainfreeze import analysis
    book = gemdb.root["brainfreeze"]
    summary = analysis.book_summary(book)
    print("     book_summary gave %d keys." % len(summary))
    gemdb.commit()
    print("     committed.")
    print()

    print("  3. Asking the app again.")
    after = _status("/")
    again = _status("/")
    if after is None and again is None:
        print("     no answer, twice.")
        print()
        print("  The app is dead and will stay dead. Its log holds a")
        print("  TypeError about `exc_info` (finding 7) standing over a")
        print("  ConflictError: Write-Write (1 objects).")
        print()
        print("  Restart it. Nothing in the book was changed.")
    else:
        print("     / -> %s, then %s." % (after, again))
        print()
        print("  The app survived. Either it had not compiled")
        print("  `book_summary` when this ran -- ask /api/stats first -- or")
        print("  the conflict this finding describes has been addressed.")


if __name__ == "__main__":
    sys.exit(compiled_code_conflict())
