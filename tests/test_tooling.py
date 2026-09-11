"""The scripts that hold the demo up, and which nothing tested.

`redeploy.py`, `run_db_tests.py`, `make_notebook.py` and `make_mcp_questions.py`
had no test naming them. Three of them keep a hand-written list in step with
something else in the repo, and a list that drifts is this project's most
frequent bug -- the MCP payload that could not start its own server, the module
`redeploy.py` silently refused to reload, the copy list that had to agree with
a REQUIRED list. Each was one forgotten name.

So these are the tests that would have caught those: they compare the list to
the thing it is supposed to describe.

Nothing here runs a script. They all need the database; what is checkable under
CPython is whether their bookkeeping still matches the repo.
"""

import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: The scripts live together in `tools/`, so that the repository root holds
#: directories rather than a drift of entry points.
TOOLS = os.path.join(REPO, "tools")


def module_constant(filename, name):
    """Read a list-of-strings constant without importing the module.

    These scripts import `gemdb` at call time but some touch it at module
    scope, and none of them can be imported under plain CPython.
    """
    with open(os.path.join(TOOLS, filename)) as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == name:
                    return [e.value for e in node.value.elts]
    raise AssertionError("%s has no %s" % (filename, name))


def package_modules():
    return sorted("brainfreeze.%s" % f[:-3]
                  for f in os.listdir(os.path.join(REPO, "brainfreeze"))
                  if f.endswith(".py") and f != "__init__.py")


class RedeployKnowsEveryModule(unittest.TestCase):
    """`redeploy.py` reloads the package in dependency ORDER, which has to be
    hand-written because no directory listing knows what depends on what.

    A hand-written list drifts. A module arrived with the JSON API
    and sat unlisted, so anyone editing it and redeploying would have kept
    running the old compiled copy with nothing to say so -- which is the exact
    failure that script exists to prevent, reintroduced one module at a time.
    """

    def test_order_names_every_module_in_the_package(self):
        order = set(module_constant("redeploy.py", "ORDER"))
        missing = [m for m in package_modules() if m not in order]
        self.assertEqual(
            missing, [],
            "redeploy.py's ORDER does not list %s -- editing one of those and "
            "redeploying would silently keep the old compiled copy"
            % ", ".join(missing))

    def test_order_names_nothing_that_does_not_exist(self):
        order = module_constant("redeploy.py", "ORDER")
        known = set(package_modules()) | {"brainfreeze"}
        stale = [m for m in order if m not in known]
        self.assertEqual(stale, [], "ORDER names modules that are gone: %s"
                         % ", ".join(stale))

    def test_the_package_itself_is_reloaded_last(self):
        order = module_constant("redeploy.py", "ORDER")
        self.assertEqual(order[-1], "brainfreeze",
                         "the package __init__ re-exports its submodules, so "
                         "it has to be reloaded after them")

    def test_money_is_reloaded_first(self):
        order = module_constant("redeploy.py", "ORDER")
        self.assertEqual(order[0], "brainfreeze.money",
                         "money has no dependencies inside the package and "
                         "everything that holds money depends on it")


class TheDatabaseRunnerRunsEverything(unittest.TestCase):
    """`run_db_tests.py` has its own hand-written list of test modules. A test
    file that is not in it runs under CPython and never inside the database --
    which is precisely where this repo's runtime differences live."""

    def collectable_modules(self):
        return sorted(
            f[:-3] for f in os.listdir(HERE)
            if f.startswith("test_") and f.endswith(".py"))

    def test_every_test_module_is_either_run_or_deliberately_excluded(self):
        listed = set(module_constant("run_db_tests.py", "MODULES"))
        # These are about files and lists, not about the database, and would
        # only be slower there. Named rather than guessed at.
        cpython_only = {
            "test_refresh",         # reads app.py's syntax tree
            "test_refresh_mcp",     # parses markdown and shas
            "test_quote_flow",      # reads the route modules' syntax trees
            "test_route_coverage",  # reads the route modules' syntax trees
            "test_imports",         # resolves imports without running them
            "test_lint",            # shells out to pyflakes under CPython
            "test_datagen",         # numpy does not exist in the database
            "test_tooling",         # this file
        }
        # test_api is NOT here on purpose. Most of it reads app.py's syntax
        # tree and skips inside the database, but its money-on-the-wire half
        # does Decimal arithmetic -- and Decimal is exactly where the two
        # runtimes differ. Serialisation only ever checked under CPython is
        # checked in the wrong place.
        unaccounted = [m for m in self.collectable_modules()
                       if m not in listed and m not in cpython_only]
        self.assertEqual(
            unaccounted, [],
            "these test modules never run inside the database, and nobody "
            "decided that: %s" % ", ".join(unaccounted))

    def test_it_does_not_list_a_module_that_is_gone(self):
        listed = module_constant("run_db_tests.py", "MODULES")
        present = set(self.collectable_modules())
        stale = [m for m in listed if m not in present]
        self.assertEqual(stale, [], "MODULES names missing files: %s"
                         % ", ".join(stale))


class ThePublishedQuestionsAreExecutable(unittest.TestCase):
    """`make_mcp_questions.py` publishes a preamble and then runs the snippets
    beneath it. Those were once two different things, so the document told a
    reader to paste three lines that could not run its own question six."""

    def test_the_preamble_binds_every_name_the_snippets_use(self):
        import refresh_mcp
        with open(refresh_mcp.DOC) as handle:
            text = handle.read()
        preamble = refresh_mcp.published_preamble(text)
        self.assertIsNotNone(preamble, "the document publishes no preamble")

        bound = set()
        for line in preamble.splitlines():
            line = line.strip()
            if line.startswith("import "):
                bound.update(p.strip().split(".")[0]
                             for p in line[len("import "):].split(","))
            elif line.startswith("from ") and " import " in line:
                bound.update(p.strip() for p in line.split(" import ")[1].split(","))
            elif "=" in line:
                bound.add(line.split("=")[0].strip())

        used, locally_bound = set(), set()
        for promise in refresh_mcp.promises(text):
            for node in ast.walk(ast.parse(promise.code.strip())):
                if not isinstance(node, ast.Name):
                    continue
                if isinstance(node.ctx, ast.Load):
                    used.add(node.id)
                else:
                    # A comprehension binds its own targets: `[r for r in xs]`
                    # uses `r` but does not need the preamble to provide it.
                    locally_bound.add(node.id)

        import builtins
        unbound = sorted(used - bound - locally_bound - set(dir(builtins)))
        self.assertEqual(
            unbound, [],
            "the published preamble does not bind %s, so a reader who pastes "
            "it cannot run the questions beneath it" % ", ".join(unbound))


if __name__ == "__main__":
    unittest.main()
