"""Routes that are looked up by name on every request, so loaded code is live.

Flask keeps the function it is given: a view handed to `app.route` at startup
is the view the app runs until it exits, however often the file is loaded
since. The model stays live because Grail updates classes in place; views
would not.

So a route module declares its routes with `ROUTES.route(...)`, which records
the rule and the function's NAME, and Flask is given a dispatcher that looks
the name up in the module on each request. Load a changed route module with
`gemdb tools/load.py` and the next request runs the new function. An ADDED
route still needs a restart: Flask builds its rule table once.

Anything a view uses has to be reached the same way -- `lookups.book()`,
`pages.render(...)` -- because `from pages import render` is a copy too.

The dispatcher is also where a view whose commit lost to another session's
is run again (conflicts.py), so no view has to say so for itself.
"""

import importlib
import sys

import conflicts


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
        # The module OBJECT, taken now, rather than looked up in
        # `sys.modules` per request: a committed module is not guaranteed to
        # stay there. Holding it loses nothing, because a loaded change
        # rebuilds the module in place.
        #
        # And not always there even now: a session that imports a committed,
        # unchanged module can find no entry for it, so every `register` was
        # a KeyError on a second test run. Importing it again hands back the
        # same committed module.
        module = sys.modules.get(self.module)
        if module is None:
            module = importlib.import_module(self.module)
        for rule, methods, name in self.table:
            app.add_url_rule(rule, endpoint=name,
                             view_func=self.dispatcher(module, name),
                             methods=list(methods))

    @staticmethod
    def dispatcher(module, name):
        def dispatch(**arguments):
            return conflicts.retrying(
                lambda: getattr(module, name)(**arguments))

        dispatch.__name__ = name
        return dispatch
