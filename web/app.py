"""Brain Freeze Insurance, as a web app running inside the database.

    gemdb web/app.py            # serves on http://127.0.0.1:5000/

Start it from the project directory. `sys.path[0]` is the script's directory
-- `web/` -- so the repository is put on the path below, before anything of
ours is imported. An import that cannot find `brainfreeze/` on disk resolves
out of the database to whatever class was last compiled there, silently.

HOW THIS IS LAID OUT

This file is the factory and the entry point, and nothing else. The pages are
in `routes_html.py`, the payloads in `routes_api.py`, the markup in
`templates.py`, the questionnaire in `forms.py`, and finding an object in
`lookups.py`.

None of them is a package, deliberately. Grail keeps a committed PACKAGE
module compiled in the database and serves that copy forever after, while a
module in a plain directory on `sys.path` is recompiled from disk each run --
measured, both ways. It is why editing a template here does not need a
`redeploy.py` first, and it is why `web/` has no `__init__.py`. Do not add
one.

WHAT IS AND IS NOT HERE

There is no ORM, no schema, no migration and no serializer, because there is
nothing to map: `gemdb.root["brainfreeze"]` is a Book of Policyholders and a
handler reads and writes those objects directly. Creating a policy is
`book.add(Policyholder(...))` followed by `gemdb.commit()`. That is the whole
persistence layer, and its absence is the point of the demo.

Every number on every screen comes from the `brainfreeze` package. A handler
that worked out a premium or a payout for itself would be a bug: two copies of
"what does this claim pay" drift by the second demo, and CUJ-2 asks an agent
to explain a refusal -- an answer it cannot give if the app and the data
disagree about the rules.

THREE CONSTRAINTS FROM GRAIL, ALL FOUND FIRST BY grail_rest_demo/app.py

1. `threaded=False`. Grail renders each Jinja template in a forked green
   thread, and the threaded dev server's per-request ContextVar cannot span
   those threads, so `url_for` inside a template cannot see the active
   request. One CPU per gem means threading buys nothing anyway.
2. One request per connection, via CloseAfterResponseHandler. A
   single-threaded server parked reading a kept-alive connection cannot accept
   the next one, so a second tab or a favicon fetch hangs everything.
3. Inline templates only. `render_template_string` is exercised in Grail's own
   suite; file-based `render_template` is not. Templates are module constants.

Every write is a POST that mutates, commits and redirects, so a refresh never
re-submits.

A QUOTE IS AN OBJECT, WHICH IS WHY THERE ARE NO HIDDEN FIELDS

`POST /quote` used to price a quote, render it, and post the five answers back
to the browser as hidden fields so that taking out a policy could work them
out again. That is state round-tripped through the client, in the one demo
whose whole argument is that these are just objects in the database -- and it
was done that way because a quote had nowhere to live. Now it does: a
`SavedQuote` goes in the book, `GET /quote/<id>` re-opens it, and
`POST /quote/<id>/accept` sells it at the price it quoted rather than at a
price computed a second time. Nothing in this file emits a hidden input; the
plan a customer picks rides on the button that picks it.

Quotes are kept in `Book.quotes`, which is deliberately not `Book.policies`:
`len(book)` is the policy count that `verify_book.py` and `tests/test_seed.py`
pin, and a quote must not move it.

THE JSON API IS THE SAME OBJECTS, NOT A SECOND MODEL

`/api/...` answers six endpoints beside the HTML routes rather than instead
of them. Every one of them serialises through
`wire.py` and none of them builds a dict of its own, because six
handlers is six places to get the money rule wrong once.

MONEY ON THE WIRE IS AN EXACT DECIMAL STRING: `"171.00"`.

`json.dumps` cannot serialise a Decimal at all, so this had to be decided
rather than inherited. A float is not one of the options -- it would put back
the two answers `brainfreeze.money` exists to remove. Integer
cents would be exact and would make every reader divide by a hundred; a
string is exact and goes straight back into `money.usd()`. And it can never
be `str(value)`: inside the database a Decimal does not keep its trailing
zeros, so `$170.10` would go out as `170.1` and the API would answer
differently in each runtime. `money.wire_usd` is where all of that lives.
`format_usd` is the display spelling -- `"$170.10"` -- and never appears in a
payload.

The JSON surface is read-only: nothing under `/api` adds or changes an object
in the book. `/api/quote` is a POST because it carries a body, and pricing
answers writes nothing. Taking out a policy and filing a claim stay POSTs
from a form, where the redirect after the write is what stops a refresh
re-submitting them.

AND ONE BEAT THAT IS NOT AUTOMATIC

A session sees the repository as of its last transaction boundary, so every
request begins with `take_new_view()` -- commit, then refresh -- or a server
started an hour ago would still be serving the book as it was an hour ago.
Read its docstring before changing it: the order matters and `abort()` is not
a substitute.
"""

import os
import sys

#: The repository, so that `brainfreeze` can be found at all. It has to
#: happen here rather than in a module this imports: a helper that adjusts
#: the path works until something commits, and then adjusts a `sys.path` the
#: caller cannot see. Measured -- `findings/09_imported_module_sys.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from flask import Flask, render_template_string
from werkzeug.serving import WSGIRequestHandler

import brainfreeze
import gemdb
import routes_api
import routes_html
from brainfreeze.money import format_usd


class CloseAfterResponseHandler(WSGIRequestHandler):
    """One request per connection -- see constraint 2 in the module docstring."""

    def handle_one_request(self):
        try:
            self.raw_requestline = self.rfile.readline(65537)
        except OSError:
            self.close_connection = True
            return
        if not self.raw_requestline:
            self.close_connection = True
            return
        if not self.parse_request():
            return
        self.close_connection = True
        self.run_wsgi()

def render(template, **context):
    """Render, with `usd` available to every template to format money.

    Money is Decimal, and `str()` on one drops the trailing zero, so `$170.10`
    would print as `170.1`. (`'%.2f'|format` would have handled that -- printf
    on a Decimal works here, contrary to what this docstring claimed for a
    while. `format(x, '.2f')` is the spelling that raises.) `format_usd` is
    used instead because it is the only one that also copes with `None`.

    It arrives in the CONTEXT rather than as a Jinja filter or global, and
    that part IS measured. `app.jinja_env.filters["usd"] = ...` does not work,
    for a reason that has nothing to do with money: Flask's `jinja_env` is a
    `cached_property`, and Grail realises cached_property WITHOUT caching, so
    `app.jinja_env is app.jinja_env` is False. Every read builds a fresh
    Environment and the registration is written to one that is discarded.
    `jinja_env.globals` is lost the same way, which is why it appears to be
    silently ignored.

    Until Grail#895 that also KILLED THE GEM rather than merely failing: the
    unknown filter raised, and jinja2's error reporting called
    `code.replace(co_name=...)` on a `compile()` result that Grail answers as
    source text, landing on `str.replace` called by keyword, which read past
    the end of an empty array. Reporting the error was what ended the session.
    """
    return render_template_string(template, usd=format_usd, **context)

def take_new_view():
    """Commit this session's compiled code, then take the latest view.

    A GemStone session sees the repository as of its last transaction
    boundary. Without this, a server that started an hour ago answers every
    request from the book as it was an hour ago: the notebook and the shell
    can commit whatever they like and the browser never learns of it. That
    made the web app the one surface of three that could not see the others'
    writes -- and it looks like a caching bug, not a transaction one.

    The order is the whole recipe, and neither half is optional.

    `gemdb.commit()` first, because `gemdb.refresh()` REFUSES while the
    session holds uncommitted work -- and it always does. Grail compiles
    Python into the database, so rendering a template is a repository write
    and a read-only request leaves the session dirty
    (findings/04_dirty_session.py).

    And never `gemdb.abort()`. It takes a new view too, and it throws away
    this session's uncommitted work -- which is the app's own compiled
    handlers. The server would lose the code it is running.

    The commit is unconditional rather than guarded by `needs_commit()`: the
    branch saves a transaction boundary that costs far less than the render
    it precedes, and the recipe is easier to trust when it reads the way the
    notebook and the README state it.
    """
    gemdb.commit()
    gemdb.refresh()

def cover_state(policy, today):
    """How to describe this policy's cover, as of a date.

    `policy_status` records the fate of a policy over its whole term, and the
    sample book's terms run either side of the present -- of 217 policies
    marked Lapsed, only 53 have actually reached their lapse date. So a screen
    that reads the stored status calls a policy lapsed while it is still
    paying claims. Compare against the date instead and say which it is.

    The term counts too, at both ends: 147 of the 900 policies have not
    started yet today, and calling those "Active" says cover is running when
    a claim filed against them would be refused.
    """
    if policy.is_in_force_on(today):
        if policy.policy_lapse_date is None:
            return ("Active", "ok")
        return ("Lapses %s" % policy.policy_lapse_date, "tag")
    if policy.no_cover_reason_on(today) == brainfreeze.REASON_POLICY_LAPSED:
        return ("Lapsed %s" % policy.policy_lapse_date, "no")
    if today < policy.policy_start_date:
        return ("Starts %s" % policy.policy_start_date, "tag")
    return ("Term ended %s" % policy.policy_end_date, "no")


def create_app():
    """Build the app and hand each surface what it needs.

    Both `register` calls take `app`; the HTML one also takes `render` and
    `cover_state`, which live here because they are about how THIS app talks
    to Grail rather than about any one page.
    """
    app = Flask(__name__)

    @app.before_request
    def before_every_request():
        """Start every handler from what the other surfaces have committed.

        Here rather than at the top of each handler so that a route added
        later cannot forget it, and on writes as well as reads: a handler
        that adjudicates a claim against an hour-old policy would be worse
        than one that merely displays it.
        """
        take_new_view()

    routes_html.register(app, render, cover_state)
    routes_api.register(app)
    return app


def serve(host="127.0.0.1", port=5000):
    create_app().run(host=host, port=port, threaded=False,
                     request_handler=CloseAfterResponseHandler)


if __name__ == "__main__":
    serve()
