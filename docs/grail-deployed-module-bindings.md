# A deployed module keeps another session's modules forever

> **CLOSED 2026-09-24: already fixed upstream. Do not implement this.**
>
> Grail `bcedc68a` ("A deployed module stays coherent with what it imported",
> 2026-09-23) makes every native module subclass `NativeModule`, with one
> instance created and committed by `install.sh` and answered in every session.
> `docs/Persistent_Modules_and_Classes.md` D8 describes the seam this closes in
> the same terms as the measurement below.
>
> It landed one day after the build this was measured on (`9a0b0fc`,
> 2026-09-17), which is the whole reason the bug looked open.
>
> Re-measured on current main, with a deployed module whose body is
> `import sys, os, json, re`:
>
> | module | on `9a0b0fc` | on current main |
> | --- | --- | --- |
> | `sys` | stale | **the caller's** |
> | `os` | stale | **the caller's** |
> | `json` | stale | **the caller's** |
> | `re` | the caller's | the caller's |
>
> That also answers the open question this plan told a reader to pull on --
> why `re` differed. It did not need the fix; the native modules did.
>
> Kept rather than deleted: the measurement is the evidence that the upstream
> fix works, and anyone on a build older than `bcedc68a` will still meet it.
> The plan below is what it looked like before that was known.

---

A fix plan for Grail. Written to be handed to someone working in
`GemTalk/Grail`; nothing in it needs the Brain Freeze repository, though that is
where it was found.

Checked against `origin/main` at `9f46b86c` (2026-09-24), measured on the
installed build `9a0b0fc`. **Not fixed.**

**The set.** Three Grail bugs were found together and are handed over together,
this one among them. Each is independent; they interact, and this is the order
worth doing them in:

| | | |
| --- | --- | --- |
| `docs/grail-logging-exc-info.md` | `Logger.error(..., exc_info=True)` raises | do first — it makes the others findable |
| `docs/grail-contextvars-session-state.md` | the current Context is committed state | design settled, ready to write |
| `docs/grail-deployed-module-bindings.md` | a deployed module keeps another session's modules | ~~open~~ — fixed upstream in `bcedc68a` |

This one is a diagnosis and an investigation plan, not a prescribed patch. The
measurement is solid; the mechanism below is inference and is labelled as such.

## The measurement

A module is written to disk, imported, and the session **commits** — which
deploys it. In a later, fresh session that imports it, the modules it holds are
not the modules the caller has:

```
RUN 2: a fresh session, importing the deployed helper

    sys    helper's is caller's : False
    os     helper's is caller's : False
    json   helper's is caller's : False
    re     helper's is caller's : True
```

The helper's source is unchanged and its own constants are correct. Nothing
raises. It simply holds different objects than the caller does.

Reproduce with `findings/09_imported_module_sys.py` in the Brain Freeze
repository (run it twice), or with four lines: write a module whose whole body
is `import sys, os, json, re`, import it, `gemdb.commit()`, then in a new
session import it again and compare each attribute with `is`.

## What it costs

The obvious tidy-up in any repository with several entry points is one helper
module that puts the project root on `sys.path`, imported for the side effect.

It works. Then something commits, and every run after it fails with

```
No module named 'yourpackage'
```

from scripts whose first statement was the thing meant to prevent exactly that.
The helper still runs, its `REPO` is still right, and its `sys.path.insert`
lands on a `sys` nobody is looking at. The error names the package rather than
the mechanism, and the helper is the last place anyone looks because it is the
thing that is supposed to be handling this.

The workaround is to repeat the three lines in every entry point and never
write the helper. That is what Brain Freeze does, in nine scripts.

**The asymmetry is worth keeping in mind while fixing it:** a path inserted by
the *running script* IS visible to everything it goes on to import, before and
after a commit alike. Only the other direction is lost.

## Likely mechanism — inference, not measurement

Grail gives each session its own instances of many modules; the
2026-07 session-state refactor (`2900b14f`, `283f086f`) added
`#GrailSysModules` and `#GrailModuleInstances` for exactly that, and
`docs/Concurrency.md` records why.

A deployed module's global bindings appear to be **resolved once, when it is
compiled and committed**, and to keep whatever instance the deploying session
had. Every later session then gets a module holding a stranger's `sys`.

`re` coming back `True` is the most interesting line in the table and the place
to start: something about `re` resolves per-session, or is shared by all
sessions, in a way `sys`, `os` and `json` are not. Whatever that difference is,
it is probably either the fix or the reason the fix is harder than it looks.

Where to read first:

* `docs/Persistent_Modules_and_Classes.md` — the canonical-modules design
* `docs/Concurrency.md` — the session-state rule and the key registry
* whatever resolves a module-global name in compiled code to a module object;
  the question is whether it can re-resolve per session instead of holding a
  reference

Compare with `03d51ac3` ("A monkey-patch is session state"), which solved a
structurally similar problem for patched names by reading an override "from a
holder `NativeModule` keeps current" rather than from a captured binding. The
same shape may apply here.

## Open questions to settle before writing code

1. Why does `re` behave differently from `sys`, `os` and `json`? Is the set
   "modules with per-session instances", or something else?
2. Is this specific to modules, or do deployed modules capture other
   session-scoped objects the same way?
3. Is per-session re-resolution affordable on every module-global read, or does
   it need the literal-association trick `03d51ac3` used to keep native-module
   attribute loads at 1.2-1.4 us?
4. Is there a case that *depends* on the current behaviour — a deployed module
   deliberately holding the deploying session's view of something?

## Acceptance

1. A module whose body is `import sys` — deployed by a committing session —
   holds the **importing** session's `sys` in every later session.
2. Therefore: a helper module that does `sys.path.insert(0, REPO)` affects the
   caller's path, before and after a commit alike.
3. The asymmetry that already works keeps working: a path inserted by the
   running script stays visible to everything it imports.
4. Whatever the answer to `re` turns out to be, it is written down — in
   `docs/Persistent_Modules_and_Classes.md` if it is by design, or in the fix
   if it was luck.

## Related, and not the same

`findings/08_script_imports.py` in Brain Freeze is the neighbouring bug: a
committed module is served **stale**, so an edited file on disk is not what
runs. This one produces a module that is not stale at all — fresh source,
correct constants — and is still not the module you wrote. Both come out of
deployment; they want fixing together or at least reading together.
