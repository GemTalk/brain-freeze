"""Does a redeploy reach a record ALREADY LOADED in a running session?

    gemdb findings/class-identity/live_reload.py     # one session, not two

Last verified against Grail 9a0b0fc (engine 4.0.0.a2), 2026-09-24: it does.
The record keeps its identity, keeps its data, and reads a class attribute
added while the process was running.

This is the half of issue #59 the other scripts here could not answer. They are
all written in two sessions on purpose -- a genuine re-import needs a genuine
new session -- which is exactly why none of them could say anything about the
LIVE case, where the process stays up.

The two-session answer is settled: edit the class, import it in a new session,
and identity survives while the record reads the new default. This asks the
other half, which is what a live schema change actually means -- the process
stays up, `importlib.reload` runs (what tools/redeploy.py does), and the
question is whether the object you are already holding sees it.

THE PACKAGE NAME IS DIFFERENT EVERY RUN, AND THAT IS NOT TIDINESS.

A committed PACKAGE module is kept by the database and served to every later
session from there, source path and all (finding 9). This script has to build
a package -- a plain module would be recompiled from disk and there would be
nothing to reload -- and it commits. So the second run on the same database is
served the FIRST run's module, whose recorded source path is wherever that run
happened to live, and the import fails reading a file that is no longer there:

    GsFile open failed for '.../tmp_live/subject.py' ... No such file

A fresh name each run is what makes it repeatable. It is the same defence
`findings/09_imported_module_sys.py` needs, for the same reason; each run does
leave one throwaway package compiled in the database, as any script that
imports something and commits does.
"""
import importlib, os, shutil, sys, time

import gemdb

HERE = os.path.dirname(os.path.abspath(__file__))

#: A package name this database has not compiled before -- see the docstring.
#: The clock is enough; Grail has no `random.Random`.
PKG_NAME = "_live_reload_%d" % time.time()
PKG = os.path.join(HERE, PKG_NAME)
if not os.path.isdir(PKG):
    os.makedirs(PKG)
open(os.path.join(PKG, "__init__.py"), "w").write("")
SRC = os.path.join(PKG, "subject.py")
open(SRC, "w").write("class Subject:\n    def __init__(self, name):\n        self.name = name\n")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

m = importlib.import_module("%s.subject" % PKG_NAME)
record = m.Subject("written before the edit")
gemdb.root["__live_check__"] = record
before_cls = type(record)
gemdb.commit()
print("  committed a record; class is", before_cls)

# The edit: add a class attribute the record was committed without.
open(SRC, "w").write(
    "class Subject:\n"
    "    added_live = 'added while the process was running'\n"
    "    def __init__(self, name):\n        self.name = name\n")

importlib.reload(m)
gemdb.commit()
print("  reloaded the module in this same session, and committed")

held = gemdb.root["__live_check__"]
print()
print("  RECORD ALREADY HELD:")
print("    type(record) is the reloaded class :", type(held) is m.Subject)
print("    isinstance(record, reloaded)       :", isinstance(held, m.Subject))
print("    data intact                        :", held.name == "written before the edit")
try:
    print("    reads the field added live         :", repr(held.added_live))
except AttributeError as e:
    print("    reads the field added live         : AttributeError:", e)

fresh = m.Subject("after")
print("    a NEW record reads it              :", repr(fresh.added_live))

del gemdb.root["__live_check__"]
gemdb.commit()
shutil.rmtree(PKG, ignore_errors=True)
print("\n  cleaned up the files; the compiled package stays in the database.")
