"""Every name a surface module imports from a sibling actually exists there.

WHY THIS EXISTS

`app.py` and the modules it registers -- `routes_html`, `routes_api`,
`lookups`, `wire` -- import `gemdb` and `flask`, so CPython cannot import them
at all. Nothing in the CPython suite loads them, and until the database runs
them a misspelled import is invisible. One was: `routes_html` asked
`templates` for a name that had never existed, and the only thing that said so
was the in-database suite failing to start, with no line number.

So the import graph is checked without being executed. For every
`from <sibling> import a, b, c` in a top-level module, the names are looked up
in that sibling's syntax tree. Nothing is imported, nothing is run, and it
catches the whole class of typo in under a second.

It is deliberately syntactic. A name bound in a way this cannot see -- inside
an `if`, by `globals()[...]` -- would be reported as missing, and that is the
right trade: the modules here bind their public names at the top level, and a
check that guesses is worse than one that is occasionally strict.
"""

import ast
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The modules that make up the running application, plus the ones they lean
#: on. All top-level: Grail serves a committed PACKAGE module from the
#: database forever, while a top-level module is recompiled from disk each
#: run, which is why the app was split into siblings rather than a package.
SURFACE = ("app.py", "routes_html.py", "routes_api.py", "templates.py",
           "forms.py", "lookups.py", "wire.py")


def tree_of(filename):
    with open(os.path.join(REPO, filename)) as handle:
        return ast.parse(handle.read(), filename=filename)


def top_level_names(tree):
    """Every name the module binds at the top level."""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


class EveryCrossModuleImportResolves(unittest.TestCase):
    def setUp(self):
        self.trees = {name: tree_of(name) for name in SURFACE}
        self.exports = {name[:-3]: top_level_names(tree)
                        for name, tree in self.trees.items()}

    def imports(self):
        """(importer, module, name) for each name taken from a sibling."""
        for filename, tree in self.trees.items():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level:
                    continue
                if node.module not in self.exports:
                    continue        # stdlib, flask, gemdb, brainfreeze
                for alias in node.names:
                    yield filename, node.module, alias.name

    def test_every_imported_name_is_defined_where_it_is_taken_from(self):
        missing = ["%s imports %s from %s, which does not define it"
                   % (importer, name, module)
                   for importer, module, name in self.imports()
                   if name not in self.exports[module]]
        self.assertEqual(missing, [], "\n  ".join([""] + missing))

    def test_no_surface_module_imports_itself(self):
        for importer, module, _name in self.imports():
            self.assertNotEqual(importer[:-3], module)

    def test_the_check_is_not_vacuous(self):
        """If the walk stops finding cross-module imports -- a rename, a move
        into a package -- every assertion above passes for the wrong reason."""
        self.assertGreater(len(list(self.imports())), 10)


if __name__ == "__main__":
    unittest.main()
