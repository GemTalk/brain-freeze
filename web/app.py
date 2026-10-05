"""Ice Cream Brain Freeze Insurance, as a web app running inside the database.

    gemdb web/app.py            # serves on http://127.0.0.1:5050/
    BRAINFREEZE_PORT=8080 gemdb web/app.py    # or anywhere else

Start it from the project directory. `sys.path[0]` is the script's directory
-- `web/` -- so the repository is put on the path below, before anything of
ours is imported. An import that cannot find `brainfreeze/` on disk resolves
out of the database to whatever class was last compiled there, silently.

LAYOUT

This file is the factory and the entry point. The pages are in
`routes_html.py`, the payloads in `routes_api.py` (serialised by `wire.py`),
the markup in `templates/` (Jinja files), the questionnaire in `forms.py`,
finding an object in `lookups.py`, rendering in `pages.py`, serving in
`serving.py`, and the route table that keeps loaded code live in `routes.py`.

An edit to any of them except this one is live in the running app once it is
loaded with `gemdb tools/load.py`, because the routes look everything up by
name on each request (routes.py). An edit to a template is live on the next
request with no load at all: the templates are files, read as they change. `web/` is not a package because
`from package import module` is still served stale after an edit
(GemTalk/Grail#1223).

NO PERSISTENCE LAYER

There is no ORM, schema, migration or serializer: `gemdb.root["brainfreeze"]`
is a Book of Policyholders and a handler reads and writes those objects
directly. Creating a policy is `book.add(Policyholder(...))` then
`gemdb.commit()`.

Every number on every screen comes from the `brainfreeze` package. A handler
that worked out a premium or a payout for itself would be a bug: the app, the
notebook and the agent must agree about the rules.

CONSTRAINTS FROM GRAIL

1. `threaded=False`. Grail renders each Jinja template in a forked green
   thread, and the threaded dev server's per-request ContextVar cannot span
   those threads, so `url_for` inside a template cannot see the request.
2. One request per connection, via CloseAfterResponseHandler. A
   single-threaded server parked reading a kept-alive connection cannot accept
   the next one, so a second tab or a favicon fetch hangs everything.
3. Not Flask's `render_template`. Grail's `cached_property` does not cache,
   so `app.jinja_env` is a new Environment on every read, which compiles every
   template on every render. The app keeps one Environment of its own over
   `templates/` instead (pages.py). And `{% import %}` needs `with context`:
   plain import subtracts `dict.keys()` from a set, and Grail's is a list.

WRITES AND PAYLOADS

Every write is a POST that mutates, commits and redirects (routes_html.py).
`/api/...` serves the same objects read-only, as payloads built by wire.py.

A FRESH VIEW PER REQUEST

A session sees the repository as of its last transaction boundary, so every
request begins with `take_new_view()` -- commit, then refresh. Read its
docstring before changing it: the order matters and `abort()` is not a
substitute.

SEVERAL AT ONCE

Deployed, several of these serve one database behind a proxy, one request at
a time each (the brain-freeze-deploy repository). A commit can then lose to another instance's;
conflicts.py says what happens next. `/healthz` and `/metrics` are for the
proxy and the monitoring agent (routes_ops.py).
"""

import os
import sys

#: The repository, so that `brainfreeze` can be found at all. Done here, in
#: the entry point, before anything of ours is imported.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from flask import Flask
from werkzeug.serving import WSGIRequestHandler

import conflicts
import gemdb
import pages
import routes_api
import routes_html
import routes_ops
import serving


class CloseAfterResponseHandler(WSGIRequestHandler):
    """One request per connection -- constraint 2 in the module docstring."""

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

def take_new_view():
    """Commit this session's work, then take the latest view.

    A GemStone session sees the repository as of its last transaction
    boundary. Without this, the app never sees what the notebook, the agent
    or `tools/load.py` committed after it started.

    Commit first, because `gemdb.refresh()` refuses while the session holds
    uncommitted work, and Grail compiles Python into the database, so the
    app's own code can be that work. Unconditional rather than guarded by
    `needs_commit()`: a commit costs far less than the render it precedes.

    Never `gemdb.abort()` in place of the commit. It takes a new view too,
    but it discards this session's uncommitted work, which can include the
    app's compiled handlers.

    Except once the commit has failed. Another instance committed some of
    the same objects first -- the cache that reading code writes -- and the
    work is then a copy of what that session already saved, which only an
    abort clears (conflicts.py). The abort is the new view.
    """
    try:
        gemdb.commit()
    except gemdb.ConflictError as conflict:
        gemdb.abort()
        print("%s: taking a new view (%s)"
              % (conflicts.SAID, str(conflict).split(";")[0]))
        return
    gemdb.refresh()

def create_app():
    """Build the app and register both surfaces onto it.

    A loaded change to a page, a template or the model is live on the next
    request (routes.py). A change to this file needs a restart.
    """
    app = Flask(__name__)
    app.extensions[pages.TEMPLATES] = pages.environment(
        os.path.join(REPO, "web", "templates"))

    @app.before_request
    def before_every_request():
        """Start every handler from what the other surfaces have committed.

        Here rather than in each handler so a new route cannot forget it,
        and on writes as well as reads: adjudicating a claim against a stale
        policy is worse than displaying one.
        """
        take_new_view()

    routes_html.register(app)
    routes_api.register(app)
    routes_ops.register(app)
    serving.install_reporting(app)
    return app


def serve(host="127.0.0.1", port=None):
    """Build the app, take a transaction boundary, then open the socket.

    Building the app compiles templates and handlers into the database as
    this session's uncommitted work. If another session (the notebook,
    `tools/load.py`) commits first, the first `take_new_view()` meets a
    write-write conflict that repeats on every request. Committing before
    `run` closes that window.

    If that commit itself conflicts -- another instance compiled the same
    code a moment earlier -- this one exits 1 rather than aborting what it
    just built, and whatever started it starts it again: the instances'
    systemd units (brain-freeze-deploy) restart it and stagger the starts.

    `port` is `BRAINFREEZE_PORT` if set, else 5050, read when the app starts.
    """
    if port is None:
        try:
            port = serving.configured_port(os.environ)
        except ValueError as wrong:
            print(wrong)
            return 1
    try:
        serving.preflight(host, port)
    except serving.PortBusy as busy:
        print(busy)
        return 1

    app = create_app()
    try:
        gemdb.commit()
    except gemdb.ConflictError as conflict:
        print("%s: another session compiled the app first; start again. (%s)"
              % (conflicts.SAID, str(conflict).split(";")[0]))
        return 1
    print(serving.banner(host, port))
    app.run(host=host, port=port, threaded=False,
            request_handler=CloseAfterResponseHandler)


if __name__ == "__main__":
    sys.exit(serve())
