"""Arm 2 of the schema-change check: does the committed record survive it?

    gemdb tests/class_identity/migration_write.py    # run this first
    gemdb tests/class_identity/migration_read.py

A fresh session, importing the edited source the ordinary way. The question is
whether the class it compiles is the one the committed record points at.

If Grail re-minted the class because of the edit, every instance committed
under the old one would be stranded: `isinstance` going False is that,
visible from Python. The record's data is not what is at risk; its
relationship to its class, which is what makes it findable by type, is.

It prints one machine-readable line per fact so a test can assert on it, then
removes the throwaway package and root key whatever the answer was.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "tmp_migration")
ROOT_KEY = "__migration_check__"


def cleanup(gemdb):
    """Leave nothing behind, whichever way the measurement went."""
    try:
        if ROOT_KEY in gemdb.root:
            del gemdb.root[ROOT_KEY]
            gemdb.commit()
    finally:
        shutil.rmtree(PKG, ignore_errors=True)


def main():
    import gemdb

    if ROOT_KEY not in gemdb.root:
        print("NOT_ARMED: run migration_write.py first.")
        return 2

    sys.path.insert(0, HERE)
    from tmp_migration.subject import Subject

    gemdb.commit()

    record = gemdb.root[ROOT_KEY]

    # `is` and `isinstance` are asked separately on purpose: they can come
    # apart, and a check that conflated them could not see it.
    print("ISINSTANCE: %s" % isinstance(record, Subject))
    print("TYPE_IS: %s" % (type(record) is Subject))
    print("TYPE_NAME: %s" % type(record).__name__)
    print("DATA_INTACT: %s" % (record.name == "written before the edit"))

    try:
        value = record.added_later
    except AttributeError:
        value = "<AttributeError>"
    print("ADDED_LATER: %s" % value)

    cleanup(gemdb)
    print("CLEANED: tmp_migration/ removed, gemdb.root[%r] deleted." % ROOT_KEY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
