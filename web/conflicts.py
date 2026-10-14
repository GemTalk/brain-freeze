"""What a request does when another session committed the same objects first.

Deployed, several instances of this app serve one database, each in a
session of its own (the brain-freeze-deploy repository). Two of them can
write the same object between their transaction boundaries, and the second
to commit then gets
`gemdb.ConflictError`: nothing it wrote is saved, and its uncommitted
changes stay in place until it aborts. That happens in two places.

A VIEW'S OWN COMMIT

Two claims filed at once both issue the next claim id, and `Book.issue`
makes both write `book.serials`, so one of them conflicts. `retrying`
aborts and runs the whole view again against the database as it now is, and
the second run draws the next number. Running a view twice is safe because
everything it did before committing was a write to the database, and the
abort took all of it back. A view must keep it that way: nothing outside the
database before its commit.

It waits a little, at random, before each new run. Instances that lost to
the same commit would otherwise start again together and collide again.

THE COMMIT THAT STARTS EVERY REQUEST

Reading code compiled into the database can cache into it, and the cache is
a write (Grail #851, and the warming in Grail's own `gemdb/admin.py`). Two
instances that both serve a page for the first time cache the same thing, and
the second `take_new_view` (app.py) conflicts on objects no view wrote. It
aborts too: what it discards is a copy of what the other session already
committed.

Under one instance neither happens, which is why the tutorial never sees it.
"""

import random
import time

from flask import Response, request

import gemdb

#: Runs of a view before the request is refused. Each loss means another
#: commit got through, so five in a row is something hammering one object,
#: not bad luck.
ATTEMPTS = 5

#: The longest wait before a new run, in seconds, grown with each loss.
BACKOFF = 0.05

#: The answer once every run has lost. A Response, not `pages.refuse`:
#: Grail's werkzeug has no 503 to raise.
BUSY = ("Too many people are writing to the book at once. Nothing you sent "
        "was saved. Try again.")

#: Printed with every conflict, and what brain-freeze-deploy's
#: terraform/monitoring.tf counts in the logs. Change one, change both.
SAID = "commit conflict"


def retrying(view):
    """Run `view()`; on a conflict, abort and run it again.

    Returns what the view returned, or 503 once `ATTEMPTS` runs have all
    lost. The abort is also a new view, so the next run sees the commit
    that beat this one.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return view()
        except gemdb.ConflictError as conflict:
            report(attempt, conflict)
            # Wait, then abort. The abort is where the next run's
            # transaction begins, and another session committing anywhere
            # in between is what makes the next run lose too: waiting after
            # it would only widen that window.
            time.sleep(random.uniform(0, BACKOFF * attempt))
            gemdb.abort()
    return Response(BUSY, status=503, mimetype="text/plain",
                    headers={"Retry-After": "1"})


def report(attempt, conflict):
    """One line for the log, saying which request lost and how often."""
    print("%s: %s %s, attempt %d of %d (%s)"
          % (SAID, request.method, request.path, attempt, ATTEMPTS,
             str(conflict).split(";")[0]))
