"""Finding 10: two sessions doing decimal arithmetic can stop a running app
answering, for good, and the reason never reaches a log.

    gemdb web/app.py                          # terminal 1, leave it up
    gemdb findings/10_shared_session_state.py # terminal 2

This script is the second session. It needs the app running, and **it will
stop the app from answering** -- that is what it demonstrates. Nothing in the
book is written or changed; restart the app and everything is as it was.

Last reproduced on Grail 9a0b0fc (engine 4.0.0.a2), 2026-09-23 -- the build
GemDB Code 1.5.0 ships, so this is what a stock install does.

FIXED UPSTREAM in Grail #1176, merged 2026-09-25. Verified on `2264a9ae`:
this script runs clean and the app keeps answering, and so does the notebook
committing under a live app. Which build you are on:

    gemdb -c 'import contextvars; print(hasattr(contextvars, "_state"))'

True means fixed. The script detects it either way and says which it saw, so
running it on a fixed build is not a wasted trip -- it is the check.

One wrinkle worth knowing on a freshly installed Grail: the FIRST call of any
module-level function after an install writes that module instance, so the
first run after an upgrade can still conflict on `_pydecimal` itself rather
than on anything here. Grail#1176 documents it; one warm-up commit clears it,
which is what `gemdb web/app.py` plus a single request already does.

WHY THIS MATTERS

`web/app.py` takes a new view before every request, and `take_new_view()`
commits first because `refresh()` refuses while a session holds uncommitted
work -- and it always does, because Grail compiles Python into the database
and rendering is therefore a repository write (finding 4).

That commit is the exposure, but not for the reason this finding first gave.
The conflict is not over anything of ours. Catch it and print
`ConflictError.conflicts` and it names the objects:

    Write-Write (5 objects):
      re.compile('50*$')                               SrePattern
      re.compile('0*$')                                SrePattern
      {<class '_pydecimal.Clamped'>: 0, ...,
       <class '_pydecimal.Inexact'>: 1,
       <class '_pydecimal.Rounded'>: 1, ...}           dict
      [0, 1]                                           PyDictCollisionBucket
      [0, 1, 0, 0]                                     PyDictCollisionBucket

That dict is a `decimal` `Context.flags`. Every decimal operation that rounds
or loses precision mutates it, and this is a money application, so both
sessions do it constantly.

A GemStone Write-Write needs the **same object**. So the two sessions are
sharing one decimal `Context` -- which they can only reach through Grail's
`contextvars`, whose last two lines are

    _top_context = Context()
    _current_context = _top_context

module-level globals in a committed module. Anything any library puts in a
`ContextVar` is shared across every session and persists in the repository.

**It is stdlib runtime state living in the repository, not anything about
compilation.** `random`, `secrets` and `re._cache` have already been moved to
per-session storage in Grail; `contextvars` has not.

WHY THE APP CANNOT RECOVER

`gemdb.abort()` would take a new view, and would also throw away this
session's uncommitted work -- which is the app's own compiled handlers. The
server would discard the code it is running. So the work stays uncommitted,
the next request re-attempts the same commit, and fails identically. The
server does not degrade. It stops answering and stays stopped.

Then finding 7 removes the evidence: Flask reports the exception by calling
`Logger.error(..., exc_info=True)`, Grail's `logging` does not accept
`exc_info`, and the `TypeError` from the reporting call replaces the
`ConflictError` that caused it. That is why this took a week to find.

WHAT THIS FINDING SAID BEFORE, AND WHY IT WAS WRONG

It said "two sessions compiling the same callable". That came from black-box
experiments -- calling a function the app had also called killed it, calling
one it had not did not -- and the inference was wrong. `/` formats money but
does not SET `Inexact`/`Rounded`; `/api/stats` aggregates and does. So "the
app had called that function" was really "the app had set those flags". The
experiments were sound; the explanation over them was not, and it pointed at
compilation, which is not what conflicts.

WHERE THE FIX BELONGS

Grail, not here: `contextvars` needs the migration `random`, `secrets` and
`re._cache` have had. A plan written to be handed to someone working in that
repository is in `docs/grail-contextvars-session-state.md`. Confirmed not
fixed on Grail origin/main at 1f2f5ed1 (2026-09-23). Tracked as issue #83.

The acceptance suite works around it: the steps that run something in a
session of their own check the app afterwards and restart it if it is gone
(`ensure_app_answering` in `features/environment.py`). The demo has no
harness, which is why DEMO.md's first trap tells the presenter to reload the
browser after the notebook beat.

Still unexplained: the two `SrePattern` objects. `re._cache` is already a
`SessionDict` in this build, so the cache is not what conflicted -- the
pattern objects themselves were written by both sessions. Fixing
`contextvars` will not clear that, and it wants its own investigation.
"""

import os
import subprocess
import sys

import gemdb

#: Not `__doc__` -- `__main__` is shared between scripts; see finding 2.
TITLE = ("Finding 10: shared stdlib state, and the app that never answers "
         "again.")

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


def shared_session_state():
    print(TITLE)
    print("-" * 70)
    print()

    if REPO not in sys.path:
        sys.path.insert(0, REPO)

    print("  1. Is the app up, and has it set the decimal flags?")
    print("     Asking /api/stats, which aggregates money and so rounds.")
    before = _status("/api/stats")
    if before is None:
        print()
        print("     The app did not answer. Start it first:")
        print("         gemdb web/app.py")
        print("     and run this again.")
        return
    print("     /api/stats -> %s.  Its flags dict is now dirty." % before)
    print()

    print("  2. This session does the same arithmetic, and commits.")
    from brainfreeze import analysis
    book = gemdb.root["brainfreeze"]
    summary = analysis.book_summary(book)
    print("     book_summary gave %d keys." % len(summary))
    try:
        gemdb.commit()
        print("     committed.")
    except Exception as error:
        # This session can lose the race too; that is the same bug from the
        # other side, and its conflicts are the interesting part.
        print("     %s" % error)
        conflicts = getattr(error, "conflicts", None) or {}
        for category, objects in conflicts.items():
            if objects:
                print("       %s: %r" % (category, objects[:3]))
        gemdb.abort()
        print("     aborted; run it again with a freshly started app.")
        return
    print()

    print("  3. Asking the app again.")
    after = _status("/")
    again = _status("/")
    if after is None and again is None:
        print("     no answer, twice.")
        print()
        print("  The app is dead and will stay dead. Its log holds a")
        print("  TypeError about `exc_info` (finding 7) standing over a")
        print("  ConflictError: Write-Write on a decimal Context's flags.")
        print()
        print("  Restart it. Nothing in the book was changed.")
    else:
        print("     / -> %s, then %s." % (after, again))
        print()
        print("  The app survived. Either it had not set those flags when")
        print("  this ran -- ask /api/stats first -- or contextvars has")
        print("  since been moved to per-session storage in Grail, which")
        print("  is what docs/grail-contextvars-session-state.md asks for.")


if __name__ == "__main__":
    sys.exit(shared_session_state())
