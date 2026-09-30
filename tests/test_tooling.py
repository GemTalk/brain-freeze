"""The scripts in `tools/` that the tutorial runs.

Several of them keep a list in step with something else in the repo, and a
list that drifts fails silently, one forgotten name at a time. So these
compare each list to the thing it is supposed to describe.

Nothing here runs a script. They all need the database; what is checkable under
CPython is whether their bookkeeping still matches the repo.
"""

import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
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


class LoadKnowsEveryModule(unittest.TestCase):
    """`load.py` imports every module, so that a changed one is rebuilt and
    committed. It lists the directories rather than keeping a list, and this
    says the listing reaches everything the app runs."""

    def load(self):
        sys.path.insert(0, os.path.join(REPO, "tools"))
        try:
            import load
        finally:
            sys.path.pop(0)
        return load

    def test_every_package_module_is_loaded(self):
        loaded = self.load().modules()
        missing = [m for m in package_modules() if m not in loaded]
        self.assertEqual(missing, [], "load.py does not load %s" % ", ".join(missing))
        self.assertIn("brainfreeze", loaded)

    def test_every_web_module_but_the_entry_point_is_loaded(self):
        loaded = self.load().modules()
        web = sorted(f[:-3] for f in os.listdir(os.path.join(REPO, "web"))
                     if f.endswith(".py") and f != "app.py")
        self.assertEqual([m for m in web if m not in loaded], [])
        self.assertNotIn("app", loaded,
                         "app.py is the entry point; importing it serves nothing")

    def test_submodules_are_named_the_way_grail_rebuilds_them(self):
        """`brainfreeze.money`, never a bare `money`: `import package.module`
        is the form that checks the file (GemTalk/Grail#1223)."""
        bare = {m.split(".", 1)[1] for m in package_modules()}
        for name in self.load().modules():
            if name in bare:
                self.fail("%s would be imported bare, not as brainfreeze.%s"
                          % (name, name))


class TheModulesTheRunnerBuilds(unittest.TestCase):
    """`run_db_tests.py` builds a module per test file and execs source into it.

    Grail leaves `module.__cached__` absent on purpose -- in CPython it names
    the compiled BYTECODE FILE, and Grail has no such file -- but a reader on
    its `exec` path looks the attribute up without a default, so executing
    into a module's `__dict__` raises `'module' object has no attribute
    '__cached__'` and every module dies before a line of it runs.

    The runner answers the question rather than dodging it: `None` is what
    CPython puts there for a module with no cached bytecode, which is true of
    every module built here. This pins that, because the line looks removable
    and the suite that would catch its removal only runs where a database is.
    """

    def runner(self):
        """Import `run_db_tests.py` itself. It touches no `gemdb` at module
        scope, unlike the siblings `module_constant` exists to avoid."""
        spec = importlib.util.spec_from_file_location(
            "run_db_tests_under_test", os.path.join(TOOLS, "run_db_tests.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_a_built_module_answers_dunder_cached(self):
        runner = self.runner()
        with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False, encoding="utf-8") as handle:
            handle.write("VALUE = 1\n")
            path = handle.name
        try:
            module = runner.load_module_from_file("probe_cached", path)
        finally:
            os.remove(path)
        self.assertEqual(module.VALUE, 1)
        self.assertIsNone(
            getattr(module, "__cached__", "absent"),
            "run_db_tests.load_module_from_file must set __cached__ = None; "
            "without it every in-database module fails on Grail before it "
            "runs. See the comment on that line.",
        )


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
            "test_mcp_questions",   # parses markdown
            "test_quote_flow",      # reads the route modules' syntax trees
            "test_route_coverage",  # reads the route modules' syntax trees
            "test_imports",         # resolves imports without running them
            "test_lint",            # shells out to pyflakes under CPython
            "test_notebook",        # reads the .ipynb and its generator
            "test_datagen",         # numpy does not exist in the database
            "test_tooling",         # this file
            # These DRIVE database sessions with subprocess, so they
            # cannot be one: run inside the database they would nest.
            "test_class_identity",
            "test_notebook_runs",   # spawns `gemdb tools/run_notebook.py`
            "test_ctrl_c",          # spawns the app under a terminal
            # And this one needs a session where `numbers` was never
            # imported, which the shared suite session cannot promise.
            "test_decimal_comparison",
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
    beneath it, so the preamble a reader pastes has to be able to run every
    question."""

    def test_the_preamble_binds_every_name_the_snippets_use(self):
        import mcp_questions
        with open(mcp_questions.DOC) as handle:
            text = handle.read()
        preamble = mcp_questions.published_preamble(text)
        self.assertIsNotNone(preamble, "the document publishes no preamble")

        # Parsed, not split on spaces: `import a.b as c` binds `c`, not `a`.
        bound = set()
        for node in ast.walk(ast.parse(preamble)):
            if isinstance(node, ast.Import):
                bound.update(a.asname or a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                bound.update(a.asname or a.name for a in node.names)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                bound.add(node.id)

        used, locally_bound = set(), set()
        for promise in mcp_questions.promises(text):
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


class TheTextFilesAreTidy(unittest.TestCase):
    """No trailing whitespace, and no tabs in Python.

    Trailing whitespace is invisible, so it is only noticed when someone next
    runs a linter -- everywhere at once, buried in a diff with real changes.
    Several files here are generated, so this also catches a generator that
    emits it.

    Markdown is the exception: a line ending in exactly two spaces is a HARD
    LINE BREAK, and stripping it would run lines together into a paragraph.
    So two spaces are allowed in a `.md` and anything else is not -- which
    also catches the three-space near-miss that does nothing at all.
    """

    #: Everything tracked that is text, by extension, so a binary file added
    #: later is not read as mojibake.
    TEXT = (".py", ".md", ".feature", ".ini", ".json", ".csv", ".html",
            ".ipynb", ".txt", ".js")

    def files(self):
        listed = subprocess.run(["git", "ls-files"], cwd=REPO,
                                capture_output=True, text=True)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        return [name for name in listed.stdout.splitlines()
                if name.endswith(self.TEXT)]

    def lines(self, name):
        with open(os.path.join(REPO, name), encoding="utf-8") as handle:
            return handle.read().splitlines()

    def test_the_check_sees_the_repository(self):
        self.assertGreater(len(self.files()), 50,
                           "git ls-files found almost nothing, so everything "
                           "below passes for the wrong reason")

    def test_no_line_ends_in_stray_whitespace(self):
        offences = []
        for name in self.files():
            markdown = name.endswith(".md")
            for number, line in enumerate(self.lines(name), 1):
                if not line.endswith((" ", "\t")):
                    continue
                if markdown and line.endswith("  ") and not line.endswith("   "):
                    continue            # a hard line break, and deliberate
                offences.append("%s:%d" % (name, number))
        self.assertEqual(offences, [], "trailing whitespace: %s"
                         % ", ".join(offences))

    def test_no_python_file_uses_a_tab(self):
        offences = ["%s:%d" % (name, number)
                    for name in self.files() if name.endswith(".py")
                    for number, line in enumerate(self.lines(name), 1)
                    if "\t" in line]
        self.assertEqual(offences, [], "tabs: %s" % ", ".join(offences))


if __name__ == "__main__":
    unittest.main()
