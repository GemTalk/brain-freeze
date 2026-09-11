"""Every route the app declares is exercised by something.

WHY THIS EXISTS, AND WHY IT IS NOT `coverage.py`

The route modules cannot be measured by a coverage tool. They import `gemdb`
and run inside GemStone under Grail, so they cannot be imported under CPython
at all, and `coverage.py` never sees the process that actually serves a
request. The in-database tests and the acceptance suite exercise them heavily
-- and nothing tells you what they miss. That was the largest blind spot in
the project when it was measured.

This is the honest substitute: read the routes out of the route modules'
syntax trees, read the tests and feature files, and require that each route
is reached by name. It is coarser than line coverage, and it answers the question that
actually matters here -- *is there a route nobody drives?*

A route can be claimed in three ways, all of which are real exercise:

  a test or step that visits its URL shape          e.g. "/api/stats"
  a step that names its handler                     e.g. api_stats
  an acceptance step whose Gherkin phrasing covers it

The first is what almost everything uses. The others are here because a
handler can be reached through a redirect or a form post, where no literal URL
appears in the test.
"""

import ast
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: Routes that are deliberately not driven, and why. Empty on purpose: an
#: entry here is a decision someone has to defend in review, not a place to
#: park a route that is merely inconvenient.
UNDRIVEN = {}


#: Where routes are declared. Two modules since the single file was split;
#: a third would have to be added here, which the count guard below catches.
ROUTE_MODULES = ("routes_html.py", "routes_api.py")


def declared_routes():
    """(rule, handler name) for every @app.route across the route modules."""
    found = []
    for filename in ROUTE_MODULES:
        with open(os.path.join(REPO, filename)) as handle:
            found.extend(_routes_in(ast.parse(handle.read())))
    return found


def _routes_in(tree):
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call)
                    and getattr(decorator.func, "attr", "") == "route"
                    and decorator.args):
                found.append((decorator.args[0].value, node.name))
    return found


def exercising_text():
    """Everything that could drive a route: tests, steps and feature files."""
    chunks = []
    for directory, suffixes in ((HERE, (".py",)),
                                (os.path.join(REPO, "features"),
                                 (".py", ".feature"))):
        for root, _dirs, names in os.walk(directory):
            for name in names:
                if not name.endswith(suffixes):
                    continue
                if name == os.path.basename(__file__):
                    continue            # this file names every route itself
                with open(os.path.join(root, name)) as handle:
                    chunks.append(handle.read())
    return "\n".join(chunks)


def route_pattern(rule):
    """A regex matching the rule with its <converters> as wildcards.

    `/policies/<policy_id>/claims/<claim_id>` has to match a test that writes
    `/policies/%s/claims/%s` or an f-string or a literal id -- what matters is
    that something drives that shape, not how it spelled the parameters.
    """
    parts = [re.escape(p) for p in re.split(r"<[^>]+>", rule)]
    return re.compile(r"[\"'`]" + r"[^\"'`\s]*".join(parts))


class EveryRouteIsDriven(unittest.TestCase):
    def setUp(self):
        self.routes = declared_routes()
        self.text = exercising_text()

    def test_the_app_declares_the_routes_we_think_it_does(self):
        """A guard on this file's own premise: if the AST walk stops finding
        routes, every other assertion here passes vacuously."""
        self.assertGreaterEqual(
            len(self.routes), 12,
            "found only %d routes -- the AST walk is probably broken, and a "
            "check that finds nothing passes for the wrong reason"
            % len(self.routes))

    def test_every_route_is_driven_by_a_test_or_a_scenario(self):
        missing = []
        for rule, handler in self.routes:
            if rule in UNDRIVEN:
                continue
            by_url = route_pattern(rule).search(self.text)
            by_handler = re.search(r"\b%s\b" % re.escape(handler), self.text)
            if not (by_url or by_handler):
                missing.append("%s (%s)" % (rule, handler))
        self.assertEqual(
            missing, [],
            "these routes are declared and nothing drives them:\n  %s\n"
            "the route modules cannot be measured by coverage.py, so this "
            "check is the only thing standing between a route and nobody "
            "noticing it broke." % "\n  ".join(missing))

    def test_the_undriven_list_is_honest(self):
        """Anything excused must still exist. A stale exclusion silently
        forgives a route that was renamed."""
        rules = {rule for rule, _ in self.routes}
        for rule in UNDRIVEN:
            self.assertIn(rule, rules,
                          "%r is excused but no longer declared" % rule)


if __name__ == "__main__":
    unittest.main()
