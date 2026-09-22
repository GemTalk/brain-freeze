# How the app runs

Design, 2026-09-17.

The app is a sample built to be demoed, and it has to be runnable by someone
who has never seen GemStone. Everything below follows from that one sentence.

## The failure this starts from

On the morning of 2026-09-17 the app was started at 08:43. It hung. Because a
working server here prints nothing, a hung one is byte-identical to a healthy
one from outside, so the hang went unnoticed and a second app was started at
09:20. Port 5000 was still held by the corpse, so the port was changed in
tracked source -- `web/app.py`, `serve(port=9090)` -- which left the code
disagreeing with about thirty references across `DEMO.md`, `README.md`,
`PLAN.md` and the acceptance harness.

Both processes had reparented to PID 1. Both held a GemStone session. The
stone allows ten.

Nothing there is exotic. Every step is what a newcomer would do, and the app
offered no way to do better.

## Decisions

Four, settled before the design:

1. **Audience.** A sample app to demo; it must be runnable by newcomers.
2. **Entry point.** `gemdb web/app.py` stays the one command. It gets smarter;
   nothing new to learn, and every existing doc reference stays true.
3. **Port.** Not configurable. Port 5000 was free the whole time -- the
   collision was our own orphan, so the fix is diagnosis, not a flag.
4. **Observability.** Startup banner, access log, and visible view exceptions.

## What was measured

This repo has been bitten by plausible guesses before -- commit 29ba480
corrected three documents that confidently explained the silence with the
wrong cause. So each mechanism below was run before it was designed around.

| Question | Result |
| --- | --- |
| `subprocess` inside Grail | works |
| `lsof` from inside Grail | runs, output parses (34 listeners found and split) |
| `print()` at startup | reaches the terminal |
| `print()` from `log_request` | **never runs -- the hook is dead** |
| `signal.alarm` | armed without error, **never delivers** |
| `os._exit` | **does not exist** in Grail's `os` (AttributeError) |
| `print()` from `@app.after_request` | works, and sees the status code |
| `@app.errorhandler(Exception)` | fires, and can print a real traceback |
| `raise error` for an HTTPException | **breaks the connection** (finding 7) |
| `return error` for an HTTPException | preserves 404, 403, and routing 404s |

Two of those killed the first draft of this design.

**`log_request` is a dead hook.** Grail ships its own `werkzeug.serving`, and
in it `log_request` is *defined* and *never called*: `run_wsgi` uses
`send_response_only`, which -- unlike `send_response` -- does not log. An
access log cannot hook there.

**Re-raising an HTTPException is what breaks it.** The first draft said the
error handler "must re-raise HTTPException so the refusals keep working."
Measured, re-raising sends Flask into the reporting path that calls
`Logger.error(..., exc_info=True)`, which raises a `TypeError` over the top of
the real exception -- finding 7, exactly -- and the client gets a dead
connection instead of a 404. Returning the exception object preserves the
status.

## Design

### 1. A new module: `web/serving.py`

`web/app.py` says of itself that it is "the factory and the entry point, and
nothing else" -- pages in `routes_html`, payloads in `routes_api`, markup in
`templates`, lookups in `lookups`. Adding preflight, banner, logging and error
reporting to it would make that docstring false.

So the serving concerns get their own module, and `CloseAfterResponseHandler`
moves into it, since it is a serving concern sitting in the factory today.

Not a package, deliberately, for the reason `app.py` already gives: Grail
keeps a committed PACKAGE module compiled in the database and serves that copy
forever, while a module in a plain directory on `sys.path` is recompiled from
disk each run.

`web/serving.py` exports:

- `port_holder(host, port)` -- who has the port, or `None`
- `preflight(host, port)` -- refuse, with a diagnosis, or return
- `banner(host, port)` -- what a newcomer reads when it starts
- `install_reporting(app)` -- access log and error visibility
- `CloseAfterResponseHandler` -- moved, unchanged

`serve()` stays in `app.py` and calls them in order.

### 2. Preflight

Probe the port with `connect_ex`, the way `features/environment.py` already
does. If it answers, find the holder with `lsof -nP -iTCP:<port> -sTCP:LISTEN`
and refuse:

```
Brain Freeze can't start: something is already using 127.0.0.1:5000.

  PID 76939   topaz ... web/app.py   started 08:43

That looks like an earlier run of this app that didn't shut down.
Stop it and try again:

  kill 76939
```

When the holder is not one of ours, the wording changes -- telling a newcomer
to kill someone else's server is bad advice:

```
Brain Freeze can't start: something is already using 127.0.0.1:5000.

  PID 4821    ControlCenter

That isn't Brain Freeze. On macOS, AirPlay Receiver uses port 5000 --
System Settings > General > AirDrop & Handoff.
```

Exit non-zero, so the wrapper's status file carries a real exit code.

If `lsof` is missing or returns nothing useful, still refuse, just without the
PID. A refusal without a name beats a confusing bind error.

### 3. Banner

After preflight, before `app.run()`:

```
Brain Freeze Insurance is running.

  Open:  http://127.0.0.1:5000/
  Stop:  Ctrl-C

Requests appear below as they arrive.
```

This is the line that ends "silence means hang." The last sentence matters as
much as the URL: it tells the reader what they are about to see, so an idle
terminal reads as idle rather than as broken.

There is a small window between the probe and the bind in which someone else
could take the port. Accepted: the bind error still surfaces, and closing the
window means holding the socket ourselves and handing it to Werkzeug, which is
more machinery than the risk earns.

### 4. Access log and visible errors

Both hang off Flask, not off Grail's serving, because that is where the hooks
actually fire.

**Access log** -- `@app.after_request`, measured working and it sees the
status:

```
GET  /policies/BF-100539            200
POST /api/quote                     200
GET  /policies/BF-999999            404
```

**Visible errors** -- `@app.errorhandler(Exception)`:

- `HTTPException` (404s, 405s, and every business refusal in
  `features/refusals.feature`): **return it**. Never re-raise.
- Anything else: print the traceback with `print()`, never through `logging`,
  then return a 500. `print` is the whole point -- `logging` is the thing that
  breaks here.

This is the repo's first working answer to finding 7. The finding stays
accurate about `Logger.error`; this routes around it.

### 5. Documentation this invalidates

The change inverts prose corrected two days ago in 29ba480, in two of the same
files, plus DEMO.md:

- `README.md` -- "It will print nothing at all, and that is what success looks
  like", and the `lsof`/`curl` recipe that follows from it
- `docs/writing-python-for-gemdb.md`
- `DEMO.md` -- "A working server prints nothing. Silence is success."

The standing advice, "ask the server rather than watching it," softens rather
than disappears: the server now tells you, and asking it is still how you
confirm.

`findings/07_logging_stub.py` gains a closing note pointing at
`install_reporting` as the way around it. The finding itself does not change.

## Testing

Unit, in `tests/`, following the existing style:

- `port_holder` returns the PID of a socket the test opened itself, and `None`
  for a free port
- `preflight` refuses on a held port and names the PID; returns on a free one
- the error handler returns an `HTTPException` unchanged and does not re-raise
- the error handler prints a traceback for a real exception and returns 500
- the banner names the configured port

Acceptance, in `features/`: the harness is unaffected -- it keeps its own port
guard at `environment.py`, which must fail before spawning anything and so
cannot be replaced by the app's.

The harness already redirects the app's output to `artifacts/app.log`
(`stdout=context.app_log, stderr=subprocess.STDOUT`), so both new behaviours
are assertable there without changing how the app is launched:

- the banner appears in `app.log` once the port opens -- the regression test
  for the morning this began
- a driven request appears in `app.log` as an access-log line

A welcome side effect: the access log becomes part of the evidence each
acceptance run already leaves behind, next to the screenshots.

No test asserts the old silence, so nothing has to be un-asserted.

## Out of scope

- **The double-stone race.** `$HOME/GemDB/bin/gemdb` decides whether to start
  the stone with an unguarded check-then-act: `gslist | awk ...` then
  `startstone`. Two invocations that both see no stone both start one, which
  is the likely cause of the two stone families running since 07:54. The file
  is generated by the GemDB extension and regenerated on update -- we cannot
  fix it here. File it upstream, alongside issue #65.
- **Session-count warnings.** Worth having; needs a way to ask the stone how
  many sessions are out, which we have not established.
- **Port configurability.** Decided against, above.
- **Graceful shutdown.** `os._exit` does not exist and signals do not deliver,
  so there is no clean in-process stop to build on. Ctrl-C terminates the
  process; that is what the banner should promise and nothing more.

## Risks

- Ctrl-C kills topaz without closing the GemStone session politely. This is
  already true today and is not made worse here, but the banner will now
  advertise it, so it is worth confirming a Ctrl-C'd session is reclaimed and
  not leaked before the wording ships.
- An access log on every request adds output during a live demo. If it proves
  distracting on stage, the fallback is to keep it and quiet the noisiest
  route, not to remove it -- the silence is what caused this.
