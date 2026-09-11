"""Make the database run the `brainfreeze` source that is on disk right now.

    gemdb redeploy.py

WHY THIS EXISTS

Grail compiles modules into the database and keeps them. Once `brainfreeze`
has been imported once, it is *deployed*: a later `import brainfreeze` in a
brand-new session returns what the database compiled, not what the file says.
Editing `brainfreeze/underwriting.py` and re-running changes nothing, and
nothing tells you so -- the tests go on passing against last week's rules.

That is not a corner case. It is what happens every time anyone edits this
package, and it cost a whole afternoon before it was understood: the database
was returning `31.499999999999996` from a float version of `annual_premium`
while the file on disk had returned exact Decimal for an hour.

WHAT IT DOES

`importlib.reload`, in dependency order, then a commit. Two details are
load-bearing and neither is obvious.

**Order matters.** Reloading a module re-executes it, and while that is
happening the modules that import it cannot resolve it. Reload a leaf before
anything that depends on it, or the dependent raises `ImportError: module ...
is canonical (deployed)`.

**Deleting from `sys.modules` is not a substitute** and makes things worse: a
deployed module removed that way cannot be imported again for the rest of the
session, which is a dead end rather than a reset.

WHAT IT DOES NOT DO

It does not migrate anything. Objects already committed keep the class they
were made with -- see `findings/03_class_identity.py`. Re-running `gemdb
seed.py` afterwards is what rebuilds the book under the new code, and that is
why the two are separate commands: one changes the rules, the other rebuilds
the data those rules made.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: Leaves first. `money` has no siblings above it; `analysis` reads everything
#: and is read by nothing; the package `__init__` re-exports and so goes last.
ORDER = [
    "brainfreeze.money",
    "brainfreeze.underwriting",
    "brainfreeze.adjudication",
    "brainfreeze.model",
    "brainfreeze.analysis",
    "brainfreeze",
]


def unlisted_modules():
    """Modules in `brainfreeze/` that ORDER does not name.

    ORDER has to be hand-written, because reload order is a dependency
    question no directory listing can answer. But a hand-written list drifts:
    a module has arrived and sat unlisted before, and anyone editing it and
    running this would have kept the old compiled copy with nothing to say
    so -- the exact failure this script exists to prevent, reintroduced one
    module at a time.

    So the ORDER is checked rather than trusted. Two lists that must agree is
    the bug; one list and a check is not.
    """
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brainfreeze")
    on_disk = set()
    for name in os.listdir(here):
        if name.endswith(".py") and name != "__init__.py":
            on_disk.add("brainfreeze.%s" % name[:-3])
    return sorted(on_disk - set(ORDER))


def redeploy():
    import importlib

    import gemdb

    missing = unlisted_modules()
    if missing:
        print("  ORDER does not list: %s" % ", ".join(missing))
        print("  Add them in dependency order, leaves first, and re-run.")
        return 2

    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    import brainfreeze                                   # noqa: F401  deploy it

    failed = []
    for name in ORDER:
        try:
            module = importlib.import_module(name)
            reloaded = importlib.reload(module)
            # Put it back where its dependents will look. reload() leaves a
            # deployed module absent from sys.modules, and the next module in
            # ORDER imports it by name.
            sys.modules[name] = reloaded
            print("  reloaded %-28s ok" % name)
        except Exception as error:
            failed.append(name)
            print("  reloaded %-28s %s: %s"
                  % (name, type(error).__name__, str(error)[:60]))

    gemdb.commit()

    from brainfreeze import underwriting
    from brainfreeze.money import usd
    sample = underwriting.annual_premium("Basic", "Low")
    exact = sample == usd("31.50") and not isinstance(sample, float)

    print()
    print("  annual_premium('Basic','Low')  %r" % (sample,))
    print("  exact money rather than float  %s" % exact)
    if failed:
        print("  MODULES THAT DID NOT RELOAD    %s" % ", ".join(failed))
        return 1
    if not exact:
        print("  The database is still running older code.")
        return 1
    print("\n  Committed. Re-run `gemdb seed.py` to rebuild the book under it.")
    return 0


if __name__ == "__main__":
    sys.exit(redeploy())
