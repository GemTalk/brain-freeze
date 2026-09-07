"""Run brain-freeze.ipynb's code cells inside the database.

    gemdb run_notebook_check.py

A notebook that errors on cell 4 in front of an evaluator is worse than no
notebook, and nothing else in the suite touches it -- the .ipynb is data, so
`unittest discover` cannot know it is broken. This executes every code cell in
order, in one namespace, the way the kernel would.

It cannot prove the *narrative*: the refresh beat only shows a change when
another session has committed in between, and this runs alone. What it proves
is that every cell executes, in order, against a real book.
"""

import io
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

NOTEBOOK = os.path.join(HERE, "brain-freeze.ipynb")

with io.open(NOTEBOOK, encoding="utf-8") as handle:
    notebook = json.load(handle)

cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
print("Running %d code cells from %s\n" % (len(cells), os.path.basename(NOTEBOOK)))

namespace = {"__name__": "__notebook__"}
failed = 0

for number, cell in enumerate(cells, 1):
    source = "".join(cell["source"])
    first = source.strip().split("\n")[0][:60]
    try:
        # `exec` rather than eval so multi-statement cells work; a cell whose
        # last line is an expression (the kernel would echo it) is executed
        # for its side effects only, which is enough to catch a broken cell.
        exec(compile(source, "<cell %d>" % number, "exec"), namespace)
        print("  cell %-2d ok    %s" % (number, first))
    except Exception:
        failed += 1
        print("  cell %-2d FAILED %s" % (number, first))
        traceback.print_exc()

print()
if failed:
    print("%d of %d cells failed." % (failed, len(cells)))
    sys.exit(1)
print("All %d code cells ran." % len(cells))
