"""Make the database run the `brainfreeze` source that is on disk right now.

    gemdb tools/redeploy.py

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

WHAT IT DOES AND DOES NOT REACH

It reaches the CODE, and — measured on Grail `9a0b0fc`, 2026-09-24 — records
already committed do see a field added to their class by it, keeping their
identity and their data, in this session and in later ones. That is
`findings/class-identity/live_reload.py`, and it is why a redeploy is not
followed by a migration script here.

It does not RESHAPE anything. Nothing it does rewrites a committed object:
a field that changed meaning still holds the old value, a field that was
removed is still on the instances that have it, and a value that needs
recomputing under the new rules is still the old value. Re-running `gemdb
tools/seed.py` is what rebuilds the book under the new code, which is why the
two are separate commands: one changes the rules, the other rebuilds the data
those rules made.

The short version: a redeploy is the only step needed to ADD; a reseed (or a
fix-up pass nobody here has had to write) is what CHANGING would need.
"""

import os
import sys

#: The repository, for the same reason and in the same way as every other
#: script in here -- see `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


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


def point_at_disk(module, name, root):
    """Point `module.__file__` at where its source is NOW. Did it change?

    THE DATABASE REMEMBERS WHERE A MODULE CAME FROM, AND THE ANSWER EXPIRES.

    A module compiled by a session that commits is kept, and the path it was
    compiled from is kept with it. `importlib.reload` re-reads that path. So
    renaming the checkout breaks a redeploy and nothing else:

        GsFile open failed for '.../Brain Freeze Insurance/brainfreeze/money.py'
        (mode 'rb'): No such file or directory

    This repository did exactly that -- it used to be `Brain Freeze Insurance`
    -- and the database went on serving the code it had been given before the
    rename, with every other command still working, so there was nothing to
    read the failure as except a broken script.

    Rewriting `__file__` first is enough: measured, `reload` then re-reads the
    file that is actually there. The alternative is Smalltalk-side --
    `importlib ___forgetCanonicalModule___:` un-deploys a module so the next
    import re-executes it -- which is not reachable from here.

    Silent when there is no source on disk to point at, because inventing a
    path turns a clear failure into a puzzling one.
    """
    path = os.path.join(root, *name.split("."))
    for candidate in (path + ".py", os.path.join(path, "__init__.py")):
        if os.path.isfile(candidate):
            if getattr(module, "__file__", None) == candidate:
                return False
            module.__file__ = candidate
            return True
    return False


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
    package = os.path.join(REPO, "brainfreeze")
    on_disk = set()
    for name in os.listdir(package):
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

    # The package itself, so that what the database serves is what is on
    # disk. Imported by name rather than by statement: the module object is
    # not wanted here, and a bare `import brainfreeze` reads to every linter
    # as a name nobody uses.
    importlib.import_module("brainfreeze")

    failed = []
    moved = []
    for name in ORDER:
        try:
            module = importlib.import_module(name)
            # Before reloading, not after: reload re-reads `__file__`, and the
            # database's copy of it can predate a rename of this checkout.
            if point_at_disk(module, name, REPO):
                moved.append(name)
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

    if moved:
        print()
        print("  %d module(s) were compiled from a path that no longer exists"
              % len(moved))
        print("  and have been re-read from this checkout. That is what a")
        print("  renamed or moved clone looks like; nothing is wrong now.")

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
    print("\n  Committed. Re-run `gemdb tools/seed.py` to rebuild the book under it.")
    return 0


if __name__ == "__main__":
    sys.exit(redeploy())
