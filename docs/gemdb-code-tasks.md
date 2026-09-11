# What this demo needs from GemDB Code

Building all five CUJs against a real database turned up work that belongs in
the extension rather than in the demo. This is that list, ordered by whether a
PRD requirement is blocked, satisfiable-but-undocumented, or merely rough.

Written 2026-09-08. Measured against GemDB `main` at `f61ac65`, and against a
working tree on `feat/mcp-server` — those two disagree about the MCP server in
ways noted below, which is itself the first item.

Evidence for the runtime items is in [`findings/`](../findings/), as scripts
that reproduce each one on your own database. The PRD requirements they block
are in [`prd-corrections.md`](prd-corrections.md).

---

## 0. Two implementations of this demo exist

[the parallel demo](https://github.com/GemTalk/GemDB_Code/blob/c9c261ac017fd7831cd29aa71b79da4ee8c1ed9b/docs/demo/brain-freeze/) (pinned at `c9c261a`) on `main` is an independent
implementation of the same PRD — its own `app.py`, `model.py`,
`underwriting.py`, `seed.py`, a Markdown copy of the PRD and a 35KB README —
built against Grail `46c2a68`. This repo was built against `c875e56`. Neither
knew about the other until 2026-09-08.

The decision has been made to standardise on this repo, which covers all five
CUJs to their two. Three things follow:

1. Decide what happens to `docs/demo/brain-freeze/` — deleted, reduced to a
   pointer, or kept as the narrative walkthrough it is better at than this repo.
2. `GemDB_Code/Claude outputs/` holds a **pre-regeneration copy of this repo's
   dataset** — 5,017 events against the current 4,993, missing the
   `underwriting_base` and `policy_lapse_date` columns. It is untracked, is not
   covered by `.gitignore`, and no longer matches anything. Delete it.
3. The two demos reached four of the same findings independently from different
   code. That is the strongest argument either of them makes that these are the
   product's to fix; see [`findings/README.md`](../findings/README.md).

## 1. Blocking — a PRD requirement cannot be met as written

**1.1 Read-only MCP drops the Python tools, so CUJ-2 has no safe setting.**
The PRD answers its own open question with "the MCP server is read-only". On
`main`, `gemdb.mcp.readOnly` hides every tool that can change the database —
and because upstream's `McpGrailToolset` inherits an empty
`readOnlySafeToolNames`, that includes `eval_python` and `compile_python`. The
tool surface is code-level, so removing Python removes the only way to answer a
question about a policyholder. The safe position and the useful position are
mutually exclusive. See [`prd-corrections.md`](prd-corrections.md) §1.

**1.2 Decide the fate of `feat/mcp-server`'s `toolsetNames:`.** That branch
names five toolsets explicitly — 17 tools: Python, execute, transaction, browse,
search — where `main` sends no `toolsetNames:` at all and therefore takes
`installedDefaultToolsetNames`, all 33, including `delete_class`,
`delete_method`, `remove_dictionary` and the SUnit runners. That third position
is exactly what 1.1 needs, and it exists already on a branch. It is the one
thing in that branch `main` does not have.

**1.3 A database can be installed without the regex engine.** The shim script
blanks `SHIM_LIB_PATH` when the library is not present at the moment it looks,
installs anyway, and writes a warning to a log that was empty here. The
resulting database starts, runs Python, seeds a 900-policy book and passes
every test in this repo — and cannot `import re`, so Flask, Django and every
other web framework fail together behind an error naming `_sre`. CUJ-3 and CUJ-4
are unreachable and nothing says why. Fail the install, or record the absence
somewhere a later session can see it. `findings/01_shim_missing.py` diagnoses it
in eight seconds; the fix is one assignment and a commit, **not** a reinstall.

**1.4 The MCP server ships off by default for a reason that has expired.**
`gemdb.mcp.enabled` defaults to `false`, and `docs/mcp-server.md` gives the
reason as waiting for an upstream cap on concurrent workers. **That cap landed:
`mcp_server#2` closed 2026-09-09**, and the fix is `MCP_MAX_SESSIONS`, default
3, plus a configurable idle timeout.

Verified here on `3c08dde` against this demo's own database. Six one-shot
`initialize` calls -- the exact pattern that once exhausted the ten-session
limit and refused even plain `topaz` -- were answered with two sessions and
four refusals carrying JSON-RPC `-32001` and an explanation. The stone never
went above four gems. `stop-server.sh` then released all of them and the port.

So the default is now resting on a retired premise, and the setting text
explains a defect that is fixed. Re-decide it. Note the cap of 3 is *itself* a
constraint worth stating in the demo, because the router plus three workers is
four of a ten-session budget the notebook and the app also draw on.

## 2. Satisfiable, but the user has to be told

**2.1 Cross-surface freshness needs two calls, not one, and the obvious one
refuses.** §5 of the PRD promises a change made in one surface is visible from
the others. It is not, without a deliberate act — and `gemdb.refresh()`, the
deliberate act, refuses, because running any code at all has already dirtied the
session. The recipe is `commit()` then `refresh()`. `abort()` is the wrong tool
and discards the notebook's earlier cells. See `findings/04_dirty_session.py`.
This wants a first-class affordance — a notebook command, or a status-bar
indication that this session's view is behind.

**2.2 `__main__` is one namespace shared by every script the database has run.**
Dispatch is by argument count, so a call can land in a different file's
function of the same name. `gemdb web/app.py` here failed with a `NameError` for a
global belonging to an unrelated script. Either scope `__main__` per script or
say plainly that script entry points must not be named `main`.
See `findings/02_main_namespace.py`.

**2.3 Editing a class compiles a different class.** A record committed under the
old class keeps its data, raises `AttributeError` for the new field, and stops
being `type(record) is TheClass`. CUJ-4 works here only because the optional
fields were declared before anything was committed — a claim about foresight,
not magic. Editing a model live in front of an evaluator shows them an
`AttributeError`. This needs to be a documented command ("re-import this module
into the database and commit"), not folklore.
See `findings/03_class_identity.py` and [`prd-corrections.md`](prd-corrections.md) §5.

**2.4 ~~Each MCP tool call is a clean slate.~~ Not on 0.7.0 -- names persist.**
This was recorded from `main`'s `docs/mcp-server.md`, and measuring it on
server `0.7.0` (`3c08dde`) gives the opposite answer. The `eval_python` tool's
own description says names bound in a call persist "for the rest of this
session, as in a REPL", and they do: `marker = 4993` in one call read back
`4993` in the next.

That decides the question the old entry raised. "Compose these named
functions" is **advice, not a trap**: an agent can import the package and bind
`book` once, then answer question after question against it, which is how the
nine questions in `docs/mcp-questions.md` were driven when verifying the
transport.

What still needs saying is which versions behave which way, since a demo
written against one and run against the other silently loses its preamble.

**2.5 `eval_python` returns a `printString` and nothing else** — no `print()`
capture, no traceback shaping, no module scope, none of what `pythonQueries.ts`
provides the notebook. An agent gets a worse Python experience than the user
does. `feat/mcp-server`'s own design note names a GemDB-specific toolset routing
Python through the notebook's semantics as the obvious follow-up.

**2.6 Publish the `gemdb` Python API to FR-3.4's bar** — enough that a user can
write a novel ad hoc query without consulting external docs.

## 3. Rough edges

**3.1 The session budget does not fit the demo.** The ceiling is ten. The MCP
front end holds one, each connected client one, each notebook one, each shell
one, the Flask app one, and the seed script one while it runs. A user midway
through CUJ-4 with two notebooks open sits around six, and `sessionRegistry()`
cannot see the MCP gems at all, so the "you are out of sessions" message names
a notebook while omitting them. The router and its workers also arrive unnamed —
`mcp_server#1`.

**3.2 A supported shape for a web app inside the database.** `threaded=False`,
one request per connection, inline templates only, and the `__main__` guard as
the last statement in the file. All four are load-bearing, all four were
rediscovered here, and `grail_rest_demo/` found three of them first.

**3.3 Rendering 900 rows takes about a minute.** Cause not yet established —
see [`grail-improvements.md`](grail-improvements.md) §Render throughput. It may
not be GemDB's to fix, but it is GemDB's to know about, because "the count is
the point" is a thing a demo wants to say.

**3.4 An exception in a view is invisible.** Flask's error handler calls
`Logger.error(..., exc_info=...)`; Grail's `logging` is a hand-written stub whose
`error` takes no keyword arguments, so the handler itself raises and the real
exception is somewhere further up the log. Two-line fix, upstream.

**3.5 No CSV import story.** FR-2.1 through FR-2.4 describe a subsystem the
product does not have. `seed.py` satisfies them for this dataset; nothing
generalises. The PRD calls the mechanism a separate workstream — it still is.

## 4. Before this repo goes public

FR-8.4 is a review gate, not a functional requirement: nothing in user-facing
content should leak the pending rebrand beyond what has been decided as public.
This repo is now `GemTalk/brain-freeze` and it is **public**, so the gate is
past due rather than pending.
