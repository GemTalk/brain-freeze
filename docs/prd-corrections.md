# Corrections to the PRD

Read this beside [`PRD_ Brain Freeze Insurance.docx`](PRD_%20Brain%20Freeze%20Insurance.docx).
Several requirements describe a system that cannot be built as written, or ask
for work that turns out not to exist. An implementer following the PRD alone
will build the wrong thing in at least four places.

Each entry quotes the requirement, says what is actually true, and cites the
evidence. Everything here was checked against a running database on 2026-09-08
(GemStone/S 3.7.5, Grail `c875e56`) or against GemDB's own source.

Nothing in the PRD is wrong about the *product*. The corrections are all about
the platform underneath it.

---

## 1. FR-4.5 — "read-only by default" contradicts GemDB's design

> **FR-4.5** The MCP server's data access is read-only by default, or if it
> supports writes, that's explicit and separately callable out.

**Not achievable, and the alternative it offers is the one to take.**
`gemdb.mcp.readOnly` exists but defaults to `false`, deliberately. GemDB's own
design note says why:

> the tools run Python and Smalltalk in the database and commit the result.
> That is the entire reason to point an agent at GemDB — a read-only server
> can browse a database the user could already browse in a notebook — so
> `gemdb.mcp.readOnly` is off by default and exists for whoever wants the
> narrower surface.
>
> — `GemDB_Code/docs/mcp-server.md`

Turning it on removes `eval_python` and `execute_code`, which are the only
tools that can answer a question about policyholders — there is no tool that
knows what a policyholder *is*. A read-only MCP server cannot run this demo.

**Write instead:** the server is a shell. It is loopback-only, `Origin` is
validated against a loopback allowlist, and it performs no authentication — so
treat it as equivalent to handing someone a terminal on the database. We ship
it with no claim-filing tools; it could still write anything.

---

## 2. FR-4.1 — the "documented command" does not exist

> **FR-4.1** A GemDB MCP server can be started locally (documented command)
> and runs "in the persistence layer" against the populated instance.

**There is no command.** The server is forked by the VS Code extension when
`gemdb.mcp.enabled` is turned on, and that setting **defaults to `false`**
(`src/config.ts`). Confirmed here: with the extension installed and the
database running, nothing was listening on either candidate port.

It ships off on purpose — GemDB's notes cite a worker cap, filed as
`mcp_server#2`.

**Write instead:** enabling MCP is a **setting**, not a command. There is still
a connection step, contrary to what a reader would infer.

---

## 3. The MCP endpoint is port 50390

Not a numbered requirement, but the address appears in planning notes as
`http://127.0.0.1:8787/mcp`. `DEFAULT_MCP_PORT` is **50390**
(`src/config.ts`), overridable with `gemdb.mcp.port`. The transport is
Streamable HTTP, loopback, no auth:

```
http://127.0.0.1:50390/mcp
```

---

## 4. FR-4.4 — cross-surface freshness is not automatic

> **FR-4.4** Answers are grounded in live data — a question asked before and
> after a change made via the web app or notebook returns updated results.

**Not without a deliberate act, and this is the most load-bearing correction
in this file**, because the requirement as written promises the opposite of
what happens.

Every notebook, the web app and each MCP client gets its own gem and its own
transaction, and a GemStone session sees the repository as of its last
transaction boundary. Measured with two concurrent sessions:

```
A: before                        902
A: needs_commit?                 True
A: after their commit, no action 902      <- the other session committed 903
A: refresh() refused: refresh() would discard uncommitted changes
A: after abort()                 903
```

Three things follow, none obvious:

- A session does **not** see another's commits until it takes a new view.
- `gemdb.refresh()` will usually **refuse**, because Grail compiles your code
  into the database, so merely having run anything leaves `needs_commit()`
  returning `True`. This is not about changing data.
- `gemdb.abort()` takes a new view but **discards the session's own
  definitions** — functions defined in earlier notebook cells stop existing.

**Write instead:** the objects are shared *and* each surface is transactional.
Re-asking after a change returns updated results once the asking session runs
`gemdb.commit()` then `gemdb.refresh()`. Make that a step in the journey, not
a footnote — it is the moment that proves the surfaces share one database.

---

## 5. FR-7.2 — "without a separate migration step" is true, but narrower than it reads

> **FR-7.2** The corresponding GemDB class definition can be updated to store
> the new fields without a separate/manual data migration step for existing
> records.

**Satisfied — for a reason worth stating, because the obvious reading is
wrong.** Adding `flavour` and `toppings` cost nothing here, and 2,172 existing
claims read them without erroring. That works because the defaults were
declared on the class **before anything was committed**:

```python
class Claim:
    flavour = None
    toppings = ()
```

Adding a field to a class that is already in use is a different matter.
Measured by adding an attribute and importing the edited source:

```
imported Claim             : <class 'brainfreeze.model.Claim'> 1947956
persisted claim's class    : <class 'brainfreeze.model.Claim'>  309322
SAME CLASS OBJECT?         : False
an existing claim reads it : AttributeError
a NEW claim reads it       : None
```

Editing a class compiles a *different* class; instances already committed keep
the one they were created under.

**Write instead:** no migration is needed for fields declared as optional with
class-level defaults up front. A field added after records exist is readable
only through `getattr(record, "field", default)` — which is what the
independent demo in `GemDB_Code/docs/demo/brain-freeze/` does throughout, for
exactly this reason. Say which of the two you are demonstrating.

Note also that `seed.py` **hides** this: re-seeding rebuilds every object from
the new class, so a source edit appears to have propagated when the objects
were in fact replaced.

---

## 6. FR-5.2 — do not ask for `sex`

> **FR-5.2** A quote form collects the same underwriting inputs used by the
> generator (age, sex, migraine/TTH history, favorite trigger, typical
> consumption speed).

`sex` is in the CSVs and carries **no weight in the risk model** — it appears
in no term of `risk_score()`. A form that asks it poses a question that cannot
change the answer, which is a bad look for an underwriting demo and invites
the obvious question about why an insurer is collecting it.

**Write instead:** five inputs — age, migraine history, tension-headache
history, favourite trigger, typical consumption speed. The app omits `sex` and
the mockups never had it.

---

## 7. FR-5.3 — was unsatisfiable as delivered; now satisfied

> **FR-5.3** Submitting the form computes a risk score, risk tier, and premium
> per available coverage plan, using logic consistent with the generator's
> underwriting model.

**"Consistent with" could not be met by the dataset as originally generated.**
Each policyholder's score started from a value drawn from `normal(45, 15)`
which was **not recorded**, so a score already in the dataset could not be
reproduced from the answers beside it. An applicant matching an existing
policy could land in a different tier, and *"why is this policy High tier?"*
had no honest answer.

Fixed on 2026-09-07 by recording `underwriting_base` as a column and deriving
the score from it rather than storing it. `tests/test_seed.py` now pins that
the derivation reproduces the stored score for all 900 policies.

**No change needed to the requirement** — it is now true. It is listed here
because it was silently false for the delivered dataset, and because anyone
regenerating the data must keep that column.

---

## 8. FR-3.2 — already satisfied, nothing to document

> **FR-3.2** The notebook connects to the local GemDB instance using a
> documented, minimal connection pattern (ideally auto-discovered by the
> extension).

The parenthetical is what happens. GemDB registers a Jupyter kernel against VS
Code's built-in `jupyter-notebook` type, so the connection step is *"pick
GemDB in the kernel picker"*. There is no connection string, driver or
configuration to document.

---

## 9. FR-2.1 – FR-2.4 — satisfied, but they describe a subsystem that is not there

> **FR-2.1** A documented, single command/procedure loads both CSVs…
> **FR-2.2** The import step is idempotent or clearly documents what happens…
> **FR-2.3** After import, a documented "smoke test" confirms success…
> **FR-2.4** Import errors (malformed CSV, GemDB not running, schema mismatch)
> produce actionable error messages.

All four are met by `gemdb seed.py`: one command, nine seconds, replaces
`gemdb.root["brainfreeze"]` wholesale (so a re-run is a clean reset, which also
satisfies FR-8.3), and prints its own smoke test.

The correction is to the framing. These read as a workstream — an import tool
with a schema mapping and an error taxonomy. There is no such thing here and
there is nothing to build: the loader is a CSV reader that constructs objects
and commits, and **"schema mismatch" in FR-2.4 is not a reachable error class**
because there is no schema to mismatch.

---

## 10. FR-7.6 — "redeploy" needs defining, and the definition has a trap

> **FR-7.6** "Redeploy" is defined precisely for this environment and
> documented as a single repeatable step.

**Still open, and it is not just "restart the app".** Restarting `gemdb app.py`
picks up an edited `app.py`. It does **not** reliably give existing objects a
changed *class* — see correction 5. And a module already compiled into the
database can be served in preference to an edited file on disk: editing
`tests/test_app.py` had no effect run after run, while edits to top-level
`app.py` in the same tree took effect immediately.

**Before answering this requirement,** settle what a redeploy has to guarantee:
new code only, or new code *and* migrated objects. They are different steps and
only the first is one command.

---

## 11. Missing entirely: the database may not be able to run a web app

The PRD assumes Flask works. On the machine this demo was built on it did not:

```console
$ gemdb -c 'import flask'
No module named '_sre'
```

`re` was unavailable, so Werkzeug's routing, Jinja2's lexer and all header
parsing were unavailable with it. The extent had been installed without the
CPython shim recorded — `install-grail.sh` blanks `SHIM_LIB_PATH` when the
library is not present at the moment it looks, and installs anyway with a
warning to a log. The database still started, ran Python, seeded, and passed
every test in this repo, because `brainfreeze/` is standard-library only.

**Add a prerequisite:** CUJ-0 should verify the extent can import `re` before
anything else, and the README does. One assignment fixes it —
`CPythonShim libraryPath: '<GRAIL_DIR>/src/c/shim/libcpython_ua.dylib'` then
`System commit` — and a full reinstall is not needed and would orphan the
seeded book.

---

## What is unaffected

FR-8.1 (offline at run time) holds — nothing reaches the network, though
installing numpy and pandas for the *generator* needs it once, and the
generator is not part of any journey.

FR-8.2 (README sequencing CUJ-0→4) is met. FR-8.3 (reset) is met by re-running
the seed. FR-8.4 (the branding review gate) is a process gate and untouched;
note that this repo's remote is currently a personal one and nothing has been
pushed.
