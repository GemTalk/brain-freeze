"""Routes that are looked up by name on every request, so loaded code is live.

Flask keeps the function it is given. A view handed to `app.route` at startup
is the view the app runs until the process ends, however many times the file
is edited, loaded and committed since. That is what made a running app ignore
a changed page while it picked up a changed model: the model is reached
through classes, which Grail updates in place, and the views were copies.

So a route module declares its routes with `ROUTES.route(...)`, which records
the rule and the function's NAME, and Flask is given a dispatcher that looks
the name up in the module on each request. Load a changed route module and
commit it, and the app's next request runs the new function -- measured on a
running app, 2026-09-29. A route that is ADDED still needs a restart: Flask's
table of rules is built once, when the app is.

Anything a view uses has to be reached the same way -- `templates.DECISION`,
`lookups.book()`, `pages.render(...)` -- because `from templates import
DECISION` is a copy too.
"""

import sys


class Routes:
    """The routes one module declares, by name."""

    def __init__(self, module):
        self.module = module
        self.table = []

    def route(self, rule, methods=("GET",)):
        def record(view):
            self.table.append((rule, tuple(methods), view.__name__))
            return view
        return record

    def register(self, app):
        # The module OBJECT, taken now, while `sys.modules` certainly has it.
        # Not looked up by name per request: a committed module is not
        # guaranteed to stay in `sys.modules` (a test runner's session lost
        # `routes_api` from it, and every JSON route answered 500). Holding
        # the object loses nothing, because a loaded change rebuilds the
        # module in place -- measured, the object a running app holds shows
        # the new functions after the next refresh.
        module = sys.modules[self.module]
        for rule, methods, name in self.table:
            app.add_url_rule(rule, endpoint=name,
                             view_func=self.dispatcher(module, name),
                             methods=list(methods))

    @staticmethod
    def dispatcher(module, name):
        def dispatch(**arguments):
            return getattr(module, name)(**arguments)

        dispatch.__name__ = name
        return dispatch
