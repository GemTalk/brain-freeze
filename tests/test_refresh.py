"""The app's transaction beat, checked against the source of `app.py`.

Run: python3 -m unittest tests.test_refresh -v

These read `app.py` as a syntax tree rather than driving it, because the
behaviour they pin cannot be reached from CPython -- `app.py` imports `gemdb`
and `flask`, and neither exists outside the database -- and it cannot be
observed from a single session inside it either. "This session went on serving
the old book after another gem committed" needs two gems, so the test that
would catch it directly is not a test this suite can run.

What is left is still worth pinning, because it is the whole of the defect
and every part of it is a mistake someone will make again:

* the app must take a new view at all -- without it a running server serves
  whatever was committed when it started, for as long as it runs;
* `gemdb.commit()` has to come first, because `refresh()` refuses while the
  session holds uncommitted work and a long-running app always does: Grail
  compiles Python into the database, so rendering one page dirties it
  (findings/04_dirty_session.py);
* `gemdb.abort()` must never appear. It takes a new view too, and it discards
  this session's compiled code -- the app's own handlers included.

tests/test_app.py drives the same rule through the test client, and only runs
inside the database.
"""

import ast
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO_ROOT, "web", "app.py")


def tree():
    with open(APP) as handle:
        return ast.parse(handle.read(), filename=APP)


def gemdb_calls(node):
    """Every `gemdb.<name>()` called under this node, in source order."""
    found = []
    for child in ast.walk(node):
        if (isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "gemdb"):
            found.append((child.lineno, child.func.attr))
    return [name for _, name in sorted(found)]


def functions(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]


def decorated_with(node, attribute):
    """The functions under `node` carrying an `@<anything>.<attribute>`."""
    out = []
    for function in functions(node):
        for decorator in function.decorator_list:
            if isinstance(decorator, ast.Attribute) and decorator.attr == attribute:
                out.append(function)
    return out


def called_names(node):
    return {child.func.id for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)}


class TheAppTakesANewView(unittest.TestCase):
    """A session sees the repository as of its last transaction
    boundary, so an app that never refreshes cannot see the notebook's or the
    shell's writes -- the one surface of three that is blind to the others."""

    def setUp(self):
        self.tree = tree()

    def refreshers(self):
        """Functions in app.py that call `gemdb.refresh()`."""
        return [f for f in functions(self.tree) if "refresh" in gemdb_calls(f)]

    def test_the_app_refreshes_somewhere(self):
        self.assertTrue(
            self.refreshers(),
            "app.py never calls gemdb.refresh(), so every request answers "
            "from the view the process started with")

    def test_it_commits_before_it_refreshes(self):
        for function in self.refreshers():
            calls = gemdb_calls(function)
            self.assertIn("commit", calls,
                          "%s refreshes without committing first; refresh() "
                          "refuses while the session holds uncommitted work, "
                          "and running any Python leaves it holding some"
                          % function.name)
            self.assertLess(calls.index("commit"), calls.index("refresh"),
                            "%s refreshes before it commits" % function.name)

    def test_it_never_aborts(self):
        self.assertNotIn(
            "abort", gemdb_calls(self.tree),
            "gemdb.abort() takes a new view and discards this session's "
            "compiled code -- the app's own handlers with it")

    def test_it_commits_before_it_opens_the_socket(self):
        """Building the app compiles every template and handler into the
        database, and until something commits that is all this session's
        uncommitted work. Another session committing in the meantime -- the
        notebook's last cell, or a redeploy -- collides with it, and the
        collision does not clear: the work stays uncommitted, so the conflict
        repeats on every request after it and the app never answers again.

        Measured. Run the notebook before touching the app, and the app is
        dead with nothing on the wire to say so."""
        serve = [f for f in functions(self.tree) if f.name == "serve"]
        self.assertTrue(serve, "app.py has no serve()")
        calls = [child for child in ast.walk(serve[0])
                 if isinstance(child, ast.Call)]

        def position(predicate):
            for index, call in enumerate(calls):
                if predicate(call):
                    return index
            return None

        commit = position(
            lambda c: isinstance(c.func, ast.Attribute)
            and c.func.attr == "commit"
            and getattr(c.func.value, "id", "") == "gemdb")
        run = position(lambda c: isinstance(c.func, ast.Attribute)
                       and c.func.attr == "run")
        self.assertIsNotNone(commit, "serve() does not commit, so the app "
                                     "carries its whole startup into its "
                                     "first request")
        self.assertIsNotNone(run, "serve() does not call run()")
        self.assertLess(commit, run,
                        "serve() opens the socket before it commits")

    def test_the_new_view_is_taken_before_every_request(self):
        hooks = decorated_with(self.tree, "before_request")
        self.assertTrue(hooks, "nothing is registered with @app.before_request, "
                               "so a handler added later would read a stale view")
        refreshers = {f.name for f in self.refreshers()}
        for hook in hooks:
            if "refresh" in gemdb_calls(hook):
                return
            if called_names(hook) & refreshers:
                return
        self.fail("the before_request hook does not reach the function that "
                  "commits and refreshes")


if __name__ == "__main__":
    unittest.main()
