"""The shape of the quote flow, read out of the surface modules' source.

Run: python3 -m unittest tests.test_quote_flow -v

`tests/test_app.py` drives these routes against a real database and skips
everywhere else, because `app.py` imports `gemdb` and `flask` and neither
exists under CPython. So the half of the quote work that is easiest to undo
by accident -- putting the answers back in the page -- would be pinned by
nothing at all outside the database. This reads the file instead, the way
`tests/test_refresh.py` reads it for the transaction beat.

Three things are pinned, and each of them is the defect rather than a detail
of the fix:

* the quote screen carries no hidden form fields. A hidden field was where a
  quote's state lived, because a quote had nowhere else to live;
* `POST /quote` writes and redirects, like every other write here, so a
  refresh re-opens the quote instead of minting a second one;
* `GET /quote/<id>` and `POST /quote/<id>/accept` exist, and accepting does
  not price the quote again. A quote that has to be recomputed to be accepted
  is not an object, whatever else is stored beside it.
"""

import ast
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Everything a browser can reach: the two route modules and the templates
#: they render. Read together, because "is any quote state in the browser"
#: is a question about the whole surface, not about one file.
SURFACES = ("app.py", "templates.py", "routes_html.py", "routes_api.py")

#: The subset that declares routes.
ROUTE_MODULES = ("routes_html.py", "routes_api.py")


def read(filename):
    with open(os.path.join(REPO_ROOT, filename)) as handle:
        return handle.read()


def source():
    return "\n".join(read(name) for name in SURFACES)


def routes(tree):
    """(rule, methods, function) for every `@app.route` in a route module.

    Flask's default when `methods` is not given is GET, and saying so here
    keeps the tests below reading like the routing table rather than like a
    walk of a syntax tree.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "route"
                    and decorator.args):
                continue
            rule = decorator.args[0].value
            methods = ("GET",)
            for keyword in decorator.keywords:
                if keyword.arg == "methods":
                    methods = tuple(item.value for item in keyword.value.elts)
            found.append((rule, methods, node))
    return found


def calls(node):
    """Every call under this node, as `name` or `owner.name`."""
    names = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            owner = child.func.value
            if isinstance(owner, ast.Name):
                names.add("%s.%s" % (owner.id, child.func.attr))
            else:
                names.add(child.func.attr)
    return names


class TheQuoteFlowKeepsItsStateInTheDatabase(unittest.TestCase):
    """The demo's argument is that these are just objects in the database,
    and the quote flow was the one place the app did the opposite."""

    def setUp(self):
        self.source = source()
        self.routes = []
        for name in ROUTE_MODULES:
            self.routes.extend(routes(ast.parse(read(name), filename=name)))

    def handler(self, rule, method):
        for a_rule, methods, function in self.routes:
            if a_rule == rule and method in methods:
                return function
        self.fail("no handler for %s %s" % (method, rule))

    def rules(self):
        return [(rule, methods) for rule, methods, _ in self.routes]

    # -- the answers stay out of the browser -----------------------------

    def test_the_app_carries_no_hidden_form_fields_at_all(self):
        self.assertNotIn(
            'type="hidden"', self.source,
            "a hidden field is a quote's state living in the browser; the "
            "plan a customer picks belongs on the button that picks it")

    # -- a quote has an address ------------------------------------------

    def test_a_quote_can_be_re_opened(self):
        self.assertIn(("/quote/<quote_id>", ("GET",)), self.rules())

    def test_a_quote_is_accepted_at_its_own_address(self):
        self.assertIn(("/quote/<quote_id>/accept", ("POST",)), self.rules())

    def test_nothing_answers_at_the_old_recomputing_address(self):
        # `POST /policies` took the five answers back off the form and priced
        # them again. There is nothing left for it to do.
        self.assertNotIn(("/policies", ("POST",)), self.rules())

    # -- and pricing one is a write --------------------------------------

    def test_posting_the_answers_stores_the_quote(self):
        made = calls(self.handler("/quote", "POST"))
        self.assertIn("SavedQuote", made,
                      "POST /quote prices a quote without keeping it")
        self.assertIn("gemdb.commit", made,
                      "a quote that is not committed is not in the database")

    def test_posting_the_answers_redirects_to_the_quote(self):
        # Every write here is a POST that mutates, commits and redirects, so
        # that a refresh cannot re-submit it. Storing a quote made this one a
        # write, and it has to join the rest.
        self.assertIn("redirect", calls(self.handler("/quote", "POST")))

    def test_accepting_does_not_price_the_quote_again(self):
        made = calls(self.handler("/quote/<quote_id>/accept", "POST"))
        self.assertNotIn(
            "brainfreeze.quote", made,
            "accepting re-prices instead of reading what was quoted, which "
            "is the round-trip again with the hidden fields taken out")
        self.assertIn("Policyholder", made)
        self.assertIn("gemdb.commit", made)


if __name__ == "__main__":
    unittest.main()
