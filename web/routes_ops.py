"""The two routes that machines ask, rather than people.

/healthz   The proxy in front of the instances (brain-freeze-deploy)
           asks every few seconds, and sends an instance no requests while it
           does not answer 200. Getting here at all means `take_new_view`
           committed and refreshed; 200 then says the book is there, 503 that
           the database answers but holds no book yet.

/metrics   The monitoring agent reads it once a minute, through the proxy's
           internal port: the public port refuses it. What is on the book and
           how full the database is. Request rates, latencies and errors are
           not here: the proxy sees every instance's requests and publishes
           those itself, and a counter kept in this module would be a write
           to a committed module, which every instance would conflict on.

Counts only, as on the home page: the money totals take seconds under Grail,
and a scrape holds one instance for as long as it runs.

Declared with `ROUTES.route` like the pages, so a loaded change is live
(routes.py).
"""

import time

from flask import Response

import gemdb
import gemdb.admin
import gemdb.sessions
import lookups
import metrics
from routes import Routes

ROUTES = Routes(__name__)

#: The 503's body. Seen by whoever runs `curl` on the machine, not a customer.
NO_BOOK = ("The database answers but holds no book. "
           "Run `gemdb tools/seed.py` once.\n")


@ROUTES.route("/healthz")
def healthz():
    if lookups.ROOT_KEY not in gemdb.root:
        return Response(NO_BOOK, status=503, mimetype="text/plain")
    return Response("ok\n", mimetype="text/plain")


@ROUTES.route("/metrics")
def prometheus_metrics():
    started = time.monotonic()
    families = book_families() + database_families()
    families.append((
        "brainfreeze_metrics_seconds", "gauge",
        "How long this page took to count, in seconds.",
        [({}, time.monotonic() - started)]))
    return Response(metrics.exposition(families),
                    mimetype=metrics.CONTENT_TYPE)


def book_families():
    """Policies, quotes and claims: what customers have done."""
    if lookups.ROOT_KEY not in gemdb.root:
        return []
    book = lookups.book()
    approved = refused = 0
    for claim in book.claims:
        if claim.is_approved:
            approved += 1
        else:
            refused += 1
    # getattr: a book committed before quotes existed has none, and a scrape
    # must not refuse the way `lookups.quotes` does for a page.
    quotes = getattr(book, "quotes", None) or {}
    accepted = sum(1 for saved in quotes.values() if saved.is_accepted)
    return [
        ("brainfreeze_policies", "gauge",
         "Policies on the book, seeded and sold.", [({}, len(book))]),
        ("brainfreeze_quotes", "gauge",
         "Quotes given, by whether one became a policy.",
         [({"accepted": "true"}, accepted),
          ({"accepted": "false"}, len(quotes) - accepted)]),
        ("brainfreeze_claims", "gauge", "Claims filed, by outcome.",
         [({"outcome": "approved"}, approved),
          ({"outcome": "refused"}, refused)]),
    ]


def database_families():
    """How full the database is, and who is logged in to it.

    Each needs a privilege GemDB's own account has (gemdb.admin's and
    gemdb.sessions' docstrings), so each is left out, not fatal, where the
    account lacks it: a scrape that fails loses every number on the page.
    """
    families = []
    try:
        size = gemdb.admin.size()
        families.append((
            "gemdb_repository_bytes", "gauge",
            "The database's extent on disk, and how much of it is free.",
            [({"part": "total"}, size["bytes"]),
             ({"part": "free"}, size["free_bytes"])]))
    except Exception as refused:
        print("metrics: no repository size (%s)" % refused)
    try:
        everyone = gemdb.sessions.all()
        system = sum(1 for s in everyone if s["name"])
        families.append((
            "gemdb_sessions", "gauge",
            "Sessions logged in to the database. The free license allows 10.",
            [({"kind": "system"}, system),
             ({"kind": "login"}, len(everyone) - system)]))
    except Exception as refused:
        print("metrics: no session count (%s)" % refused)
    return families


def register(app):
    """Add the health check and the metrics page to `app`."""
    ROUTES.register(app)
