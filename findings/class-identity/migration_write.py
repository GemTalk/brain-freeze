"""Arm 1 of the schema-change check: commit a record, then edit its class.

    gemdb findings/class-identity/migration_write.py
    gemdb findings/class-identity/migration_read.py     # the answer is there

Two processes, because a genuine re-import needs a genuine new session.
Compiling the edited source with `exec` in this one would land in a different
module and prove nothing -- the same reason `03_class_identity.py` is written
in two runs.

This arm does the ordinary thing a schema change does: a class is written,
instances of it are committed, and only THEN does someone add a class
attribute to it. `commit_write.py` next door already establishes that an
UNEDITED class keeps its identity across sessions, so anything this pair
measures is caused by the edit alone.

It writes a throwaway package under findings/class-identity/tmp_migration/ and
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

    # Committing after the import is what keeps the compiled class -- their
    # rule 1, and the precondition for this check meaning anything. Without
    # it the class is a throwaway and the next session recompiles it for
    # reasons that have nothing to do with the edit.
    gemdb.commit()

    gemdb.root[ROOT_KEY] = Subject("written before the edit")
    gemdb.commit()

    write_module(AFTER)

    print("ARMED: a record is committed under the unedited class, and the")
    print("       class on disk has since gained `added_later`.")
    print("       Now run: gemdb findings/class-identity/migration_read.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
