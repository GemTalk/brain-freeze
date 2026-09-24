"""Run every code cell of `brain-freeze.ipynb`, in order, in one session.

    gemdb tools/run_notebook.py          # all of them
    gemdb tools/run_notebook.py 5        # stop after cell 5

Cells are numbered from 1, the way the notebook UI shows them and the way
`DEMO.md` beat 5 refers to them ("run cell 11 first"). A runner that counted
from 0 would disagree with the document it exists to protect.

WHY THIS EXISTS

Beat 5 of `DEMO.md` is the notebook, and at seven minutes it is the longest
beat in the demo. Nothing ran it. `tests/test_notebook.py` parses every cell
and checks the first one puts the repository on the path -- which it added
after the notebook shipped for weeks unable to import its own model -- but
parsing is not running, and the interesting failures here are not syntactic.
They are `statistics.median` ending the session on a Decimal, or floor division
raising for money, or a repr that is fine under CPython and not in here.

WHAT "IN ORDER, IN ONE SESSION" BUYS

A kernel gives the notebook one namespace and one database session for the
whole document, so cell 7 sees what cell 3 bound and every cell shares one
transaction. Running the cells separately would test something nobody does.

The last expression of a cell is evaluated and its repr printed, because that
is what a kernel shows and it is frequently the whole point of the cell -- cell
1 ends with a bare `book`. A broken `__repr__` breaks the demo in front of the
room and would pass a test that only executed statements.
"""

import json
import os
import sys

#: The repository, for the same reason and in the same way as every other
#: script in here -- see `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

NOTEBOOK = os.path.join(REPO, "brain-freeze.ipynb")


def code_cells():
    with open(NOTEBOOK, encoding="utf-8") as handle:
        document = json.load(handle)
    return ["".join(cell["source"])
            for cell in document["cells"] if cell["cell_type"] == "code"]


def split_off_last_expression(source):
    """(statements, trailing expression or None), as SOURCE TEXT.

    NOT with `ast`. Grail's `ast.parse` does not return a tree at all -- it
    answers an opaque `_ParsedExpr` whose only attributes are `mode` and
    `source`, so there is no `body` to walk and no way to rebuild a node.
    (The syntax-tree tests in `tests/` are all CPython-side for this reason.)

    So the split is done the one way both runtimes agree on: find where the
    last top-level statement begins, and ask the compiler whether the text
    from there is an expression. If it compiles in "eval" mode it is one.
    """
    lines = source.splitlines()
    start = None
    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if lines[index][:1] not in (" ", "\t"):
            start = index
            break
    if start is None:
        return source, None

    return "\n".join(lines[:start]), "\n".join(lines[start:])


def run_cell(source, namespace, where):
    """Execute one cell the way a kernel does, and show its last expression.

    Whether the trailing statement is an EXPRESSION is settled by trying to
    evaluate it, not by compiling it first and looking. Grail's `compile()` is
    lazy -- it answers the source text rather than a code object -- so a
    `for` loop compiles happily in "eval" mode and only fails when eval runs
    it. That failure arrives before any of the statement executes, so falling
    back to `exec` here cannot run anything twice.
    """
    statements, tail = split_off_last_expression(source)
    if statements.strip():
        exec(compile(statements, where, "exec"), namespace)
    if not (tail and tail.strip()):
        return
    try:
        value = eval(compile(tail, where, "eval"), namespace)
    except SyntaxError:
        exec(compile(tail, where, "exec"), namespace)
    else:
        if value is not None:
            print(repr(value))


def run_notebook():
    stop_after = int(sys.argv[1]) if sys.argv[1:] else None

    cells = code_cells()
    # One namespace for the whole document, as a kernel gives it. `__name__`
    # is not "__main__": every script this database has ever run shares that
    # one namespace (findings/02_main_namespace.py), and a cell defining
    # something there would collide with whatever ran last.
    namespace = {"__name__": "brain_freeze_notebook"}

    for index, source in enumerate(cells):
        number = index + 1
        if stop_after is not None and number > stop_after:
            break
        print("\n=== cell %d " % number + "=" * 46, flush=True)
        try:
            run_cell(source, namespace, "<cell %d>" % number)
        except Exception as error:
            print()
            print("  CELL %d FAILED: %s: %s" % (number, type(error).__name__, error))
            print()
            print("  The notebook is beat 5 of the demo. Fix the cell, then")
            print("  regenerate with `python3 tools/make_notebook.py`.")
            return 1

    print()
    print("OK -- %d cells, in order, in one session." % len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(run_notebook())
