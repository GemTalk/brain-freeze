"""Finding 3: editing a class compiles a different class, and on this Grail
`isinstance` does not survive it.

    gemdb findings/03_class_identity.py     # run it TWICE

Run 1 creates a record under the original class and then edits the class on
disk. Run 2 is a fresh session that imports the edited source normally and
compares. Two runs, because a genuine re-import needs a genuine new session --
doing it with `exec` in one process would compile into a different module and
prove nothing.

It writes a throwaway package under findings/tmp_subject/ and one throwaway
key in `gemdb.root`, and removes both at the end of run 2. It never touches
`brainfreeze/`.

WHY THIS MATTERS

CUJ-4's claim is that adding a field to a live database costs nothing. True
here, but for a narrower reason than it sounds: `Claim.flavour = None` and
`Claim.toppings = ()` were class attributes **before anything was committed**,
so a record written without them reads the default through the class.

Adding a field to a class already in use is a different thing. A record
committed under the old class keeps its data, raises AttributeError for the
new field, and is no longer `type(record) is TheClass`. On Grail c875e56 it is
no longer `isinstance(record, TheClass)` either -- which contradicts
`GemDB_Code/docs/demo/brain-freeze/model.py`, whose rule 2 records `isinstance`
continuing to work, measured on Grail 46c2a68.

Both measurements are reproducible. **If run 2 prints `isinstance: True` on
your Grail, that is the interesting result** -- the behaviour changed between
those versions, and the Grail team should be told which one is intended.

Either way `type(obj).__name__` survives both, which is why that demo's rule 3
(find records by index, not by `isinstance`) is the right advice.
"""

import os
import shutil
import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
TITLE = "Finding 3: editing a class compiles a different class."

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "tmp_subject")
ROOT_KEY = "__finding_03__"

BEFORE = '''"""A throwaway class, so this finding never touches brainfreeze/."""


class Subject:
    def __init__(self, name):
        self.name = name
'''

AFTER = BEFORE + '''
    added_later = "added after the record was committed"
'''


def write_module(source):
    if not os.path.isdir(PKG):
        os.makedirs(PKG)
    for name, text in (("__init__.py", ""), ("subject.py", source)):
        with open(os.path.join(PKG, name), "w") as handle:
            handle.write(text)


def describe(record, klass):
    print("    %-24s %s" % ("type(record)", type(record)))
    print("    %-24s %s" % ("the imported class", klass))
    print("    %-24s %s" % ("type(record) is C", type(record) is klass))
    print("    %-24s %s" % ("isinstance(record, C)", isinstance(record, klass)))
    print("    %-24s %r" % ("type(record).__name__", type(record).__name__))
    try:
        value = repr(record.added_later)
    except AttributeError as error:
        value = "AttributeError: %s" % error
    print("    %-24s %s" % ("record.added_later", value))


def arm_one(gemdb):
    print("  RUN 1 -- create a record under the class as first written\n")
    write_module(BEFORE)
    sys.path.insert(0, HERE)
    from tmp_subject.subject import Subject
    gemdb.commit()                       # keep the compiled class (their rule 1)

    gemdb.root[ROOT_KEY] = Subject("written before the edit")
    gemdb.commit()
    describe(gemdb.root[ROOT_KEY], Subject)

    write_module(AFTER)                  # the edit, on disk, uncompiled
    print("\n  Added `added_later` to the class on disk.")
    print("  Now run this script again -- a NEW session, importing the")
    print("  edited source the ordinary way:\n")
    print("      gemdb findings/03_class_identity.py")
    return 0


def arm_two(gemdb):
    print("  RUN 2 -- a fresh session, importing the edited source\n")
    sys.path.insert(0, HERE)
    from tmp_subject.subject import Subject
    gemdb.commit()

    record = gemdb.root[ROOT_KEY]
    describe(record, Subject)

    fresh = Subject("written after the edit")
    print("\n    %-24s %r" % ("a NEW record reads it", fresh.added_later))

    same = type(record) is Subject
    iso = isinstance(record, Subject)
    print()
    print("  The record kept its data and did not gain the new attribute.")
    if not same and not iso:
        print("  Its class is NOT the class the edited source compiles, and")
        print("  `isinstance` does not hold either. This matches what this")
        print("  repo measured on Grail c875e56 and contradicts the")
        print("  GemDB_Code demo's rule 2, measured on 46c2a68.")
    elif not same and iso:
        print("  Its class is not the same object, but `isinstance` still")
        print("  holds -- which is what the GemDB_Code demo reports. Your")
        print("  Grail behaves as 46c2a68 did. Worth telling both authors.")
    else:
        print("  Identity survived the edit entirely. That matches neither")
        print("  measurement; note your Grail version and say so.")

    del gemdb.root[ROOT_KEY]
    gemdb.commit()
    shutil.rmtree(PKG, ignore_errors=True)
    print("\n  Cleaned up: findings/tmp_subject/ removed, gemdb.root[%r] deleted."
          % ROOT_KEY)
    return 0


def main():
    import gemdb
    print(TITLE)
    print("-" * 70)
    if ROOT_KEY in gemdb.root:
        return arm_two(gemdb)
    return arm_one(gemdb)


if __name__ == "__main__":
    sys.exit(main())
