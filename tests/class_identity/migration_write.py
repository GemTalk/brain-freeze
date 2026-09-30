"""Arm 1 of the schema-change check: commit a record, then edit its class.

    gemdb tests/class_identity/migration_write.py
    gemdb tests/class_identity/migration_read.py     # the answer is there

Two processes, because a genuine re-import needs a genuine new session:
compiling the edited source with `exec` in this one would land in a different
module and prove nothing.

This arm does what a schema change does: a class is written, an instance of
it is committed, and only THEN is a class attribute added to it.

It writes a throwaway package under tests/class_identity/tmp_migration/ and
one throwaway key in `gemdb.root`. `migration_read.py` removes both.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "tmp_migration")
ROOT_KEY = "__migration_check__"

#: The class as first written, and the same class after someone adds a class
#: attribute to it. One added line: that is the whole edit under test.
BEFORE = '''"""A throwaway class, so this check never touches brainfreeze/."""


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


def main():
    import gemdb

    write_module(BEFORE)
    sys.path.insert(0, HERE)
    from tmp_migration.subject import Subject

    # Committing after the import is what keeps the compiled class. Without
    # it the next session recompiles the class for reasons that have nothing
    # to do with the edit, and the check means nothing.
    gemdb.commit()

    gemdb.root[ROOT_KEY] = Subject("written before the edit")
    gemdb.commit()

    write_module(AFTER)

    print("ARMED: a record is committed under the unedited class, and the")
    print("       class on disk has since gained `added_later`.")
    print("       Now run: gemdb tests/class_identity/migration_read.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
