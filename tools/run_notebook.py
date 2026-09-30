"""Run every code cell of `brain-freeze.ipynb`, in order, in one session.

    gemdb tools/run_notebook.py          # all of them
    gemdb tools/run_notebook.py 5        # stop after cell 5

Cells are numbered from 1, the way the notebook UI shows them.

The notebook is step 4 of the tutorial. `tests/test_notebook.py` parses it
under CPython, but the failures that matter are the ones only the database
shows: a Decimal that `statistics.median` cannot take, floor division on
money, a repr that differs.

A kernel gives the notebook one namespace and one session for the whole
document, so this does the same: later cells see what earlier ones bound.
The last expression of a cell is evaluated and its repr printed, as a kernel
shows it, so a broken `__repr__` fails here too.
"""

import json
import os
import sys

#: The repository, to find the notebook. This runner deliberately does NOT put
#: it on `sys.path`: a kernel does not, so the notebook's first cell has to,
#: and a runner that did it for the notebook would hide a missing path cell.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTEBOOK = os.path.join(REPO, "brain-freeze.ipynb")


def code_cells():
    with open(NOTEBOOK, encoding="utf-8") as handle:
        document = json.load(handle)
    return ["".join(cell["source"])
            for cell in document["cells"] if cell["cell_type"] == "code"]


def split_off_last_expression(source):
    """(statements, trailing expression or None), as SOURCE TEXT.

    Not with `ast`: Grail's `ast` cannot be walked the way CPython's can (see
    `ast_is_usable` in tests/test_api.py). So this finds where the last
    top-level statement begins, and `run_cell` decides whether it is an
    expression.
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

    Whether the trailing statement is an expression is settled by evaluating
    it, not by compiling it first: Grail's `compile()` is lazy, so a `for`
    loop compiles in "eval" mode and only fails when evaluated. It fails
    before any of it runs, so falling back to `exec` runs nothing twice.
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
    # One namespace for the whole document, as a kernel gives it.
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
            print("  The notebook is step 4 of the tutorial: fix the cell in")
            print("  brain-freeze.ipynb.")
            return 1

    print()
    print("OK -- %d cells, in order, in one session." % len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(run_notebook())
