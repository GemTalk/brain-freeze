# The demo, as a script

Twenty minutes, nine beats, one argument: **there is one database, several ways
into it, and nothing in between.** No ORM, no schema, no migration, no
serialisation format, no connection string.

This is the presenter's copy. [`../README.md`](../README.md) is the walkthrough
and carries every command with its real output; this says what to *do*, in what
order, what to say while it happens, and what to do when something goes wrong.

Read the recovery notes before you stand up. The one that matters is at the
end: **the stone allows ten sessions**, and every `gemdb` command takes one.

---

## Before the room

Ten minutes before, not one. The first render compiles templates into the
database and is the slowest thing in the demo; you do not want an audience
watching it.

```sh
export PATH="$HOME/GemDB/bin:$PATH"     # not needed in a VSCodium terminal
cd ~/GemTalk/"Brain Freeze Insurance"
```

**1. Check the database can run a web framework.** If this fails, nothing else
will, and the error will not tell you why.

```sh
gemdb -c 'import re; print("re works:", bool(re.match(r"a+", "aaa")))'
```

Anything other than `re works: True` — stop and see "Before you start" in the
README. It is one assignment, not a reinstall.

**2. Seed a clean book.** Nine seconds. Do this even if you seeded yesterday;
a rehearsal leaves policies bought and claims filed.

```sh
gemdb tools/seed.py
```

Last line should be `Replaced gemdb.root["brainfreeze"]. Committed.`

**3. Start the app and warm it.**

```sh
gemdb web/app.py
```

In another terminal, once it says it is serving:

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/
```

`200`. **Do not skip this.** The warm-up is not superstition: the first request
is the slow one, and until the app has answered once it is carrying its whole
startup as uncommitted work.

**4. Set VSCodium up once, and never leave it during the demo.**

`Cmd+Shift+P` → *Preferences: Open User Settings (JSON)*:

```json
"claudeCode.preferredLocation": "panel",
"workbench.externalUriOpeners": { "127.0.0.1": "simpleBrowser.open" }
```

The second is the one that keeps you in the editor: every `127.0.0.1` link — in
this document's preview, or in terminal output — then opens in VSCodium's
built-in **Simple Browser**, in a tab beside your code, instead of throwing you
into Chrome. Without it you get a "how do you want to open this" prompt every
time, which is worse in front of people than either answer.

Read this script in the preview, not the source: open it and press
`Cmd+Shift+V`. That is what makes the links below clickable.

**5. Get an MCP server listening on 50390, then start the agent. In that
order.**

Check first — this is the only thing that matters, whoever started it:

```sh
lsof -nP -iTCP:50390 -sTCP:LISTEN
```

If nothing is listening, start one and check the answers at the same time:

```sh
python3 tools/refresh_mcp.py --verify
```

Ends `9 kept, 0 broken`, reports the server's version and tool count, and
leaves it running. If it borrows one that was already up it says so and does
not stop it on the way out. If something is broken you have drifted from a
fresh seed — reseed and re-run.

There are two things that can serve this port and it is worth knowing which
you have. `tools/refresh_mcp.py` stages a payload under `~/GemDB/mcp/` and
runs `run-server.sh` from there. The GemDB extension can also serve it, via
`gemdb.mcp.enabled` — but **that setting only exists in some builds of the
extension**, and if VSCodium greys it out as an unknown setting then yours is
not one of them and the script above is your route. Do not spend demo time on
this; the `lsof` line answers the only question you have.

**The order is load-bearing.** Claude Code connects to that server when its
session starts. If nothing is listening at that moment, the agent comes up with
no `gemdb` tools and stays that way for the whole session — no error, no retry,
just an absence. You do not want to find that out at beat 7.

So: server listening, *then* start Claude Code in the panel. Confirm inside the
agent with `/mcp` — you want `gemdb` connected. If it is missing, restart the
agent; the server being up now does not rescue a session that started before
it.

**6. Lay the window out, and leave it alone.** Everything below is a tab or a
panel in the same VSCodium window.

| Where | What |
| --- | --- |
| Editor tab | [the app](http://127.0.0.1:5000/) in Simple Browser — click it from this preview |
| Editor tab | `brain-freeze.ipynb`, kernel picker set to **GemDB** |
| Editor tab | `brainfreeze/model.py` |
| Terminal A | the running app — you will not touch it again |
| Terminal B | free, for the shell beats |
| Panel | Claude Code, started **after** the folder opened, `/mcp` showing `gemdb` |

Drag the Simple Browser tab into a split beside the editor. Beat 6 is you
clicking refresh in one half while a terminal in the other half changes the
database, and it reads badly if either is hidden.

---

## The run of show

Times are what the beat takes when it goes well. The whole thing is twenty
minutes and there is slack in it.

### 1 — An insurance company (1 min)

Open the Simple Browser tab. Say what it is: nine hundred policyholders, a
risk band, what each has claimed. Click into one.

**Do not explain the architecture yet.** The beat only works if they have first
decided this is an ordinary web app.

> "Brain freeze insurance. Mock company, real dataset — nine hundred
> policyholders, five thousand cold treats, two thousand claims."

### 2 — A claim, and the arithmetic behind it (3 min)

Go to **BF-100332**. Type it into the box and press Find. Clean history,
Standard plan, nothing claimed yet, so nothing on screen competes with the
point.

File a claim. Describe an episode: a slushie, straight from the freezer, a lot
of it, pain 9, lasting longer than ten minutes.

The decision screen is the beat. Four figures: what it was assessed at, what
the episode cap took off, the deductible, what it pays.

> "Nobody typed an amount. The claimant described what happened, and the rules
> worked out what that is worth. The app did not do this arithmetic — it asked
> the same function the notebook and the agent will ask in a minute, and
> printed the answer."

Then file a second claim on **BF-100092**, which has one approval left. It
pays. File a third and it is refused, and the refusal names the rule rather
than apologising.

### 3 — The reveal (1 min)

Now switch to Terminal A and show what is running.

```
gemdb web/app.py
```

> "That is the whole command. There is no connection string in this repository
> — grep for one. There is no driver, no pool, no ORM. The web app is running
> *inside* the database, and `gemdb.root` is the root namespace. The policy you
> were just looking at is an object, not a row."

This is the pivot. Everything after it is the same claim from a different
angle.

### 4 — The same objects over curl (2 min)

Terminal B. Split it beside the Simple Browser so both are on screen:

```sh
curl -s localhost:5000/api/policy/BF-100539 | python3 -m json.tool | head -30
```

> "Same objects, no second model behind it. And look at the money."

```sh
curl -s localhost:5000/api/stats | python3 -m json.tool | head
```

Point at `"premium": "92081.22"`. A string, not a number.

> "`json.dumps` cannot serialise a decimal at all, so the wire format had to be
> decided rather than inherited. Not a float — that puts back the rounding
> error we removed from the data. Not integer cents — exact, but every reader
> has to divide by a hundred. A string is the same text the model already
> reads, so a figure goes back in unchanged."

### 5 — The notebook (3 min)

Switch to the `brain-freeze.ipynb` tab. Pick the **GemDB** kernel if it is not
already picked.

> "No connection step. Picking the kernel *is* the connection — the kernel is a
> session."

Run the first cells. Stop on the introspection cell:

```
class            : Policyholder from brainfreeze.model
answers to       : 33 public names
actually stored  : 15
```

> "Thirty-three names, fifteen of them stored. The rest are computed when you
> ask. `risk_tier` is not a column that could drift out of step with the data.
> It is a question the object answers."

Then the map cell, which is there so nobody has to leave the notebook to write
their own question. Then the chart — ten lines of Python, because there is no
matplotlib and none is needed.

If you have time, stop on loss ratio by band. High is cheaper to carry than
Medium. That is a real finding about the data, not a scripted one.

### 6 — The beat worth slowing down for (2 min)

**This is the demo.** If you only get one thing across, get this one.

Leave the Simple Browser on [BF-100184](http://127.0.0.1:5000/policies/BF-100184).
It is active. Say so out loud.

Terminal B:

```sh
gemdb tools/lapse.py BF-100184
```

> "Different process. Different session. It does not know the web app exists."

Refresh the Simple Browser — the circular arrow in its toolbar, or `Cmd+R` with
it focused. The policy is lapsed. Try to file a claim on it: refused
before a word is typed, and told why.

> "No restart. No reload. No cache to invalidate, no message queue, no polling.
> A session sees the database as of its last transaction boundary, so the app
> takes a new view before every request. That is the only reason this works,
> and it is four lines."

Put it back, so the next run starts where this one did:

```sh
gemdb tools/lapse.py BF-100184 --reinstate
```

### 7 — The agent (3 min)

Switch to the Claude Code window you started in step 4 — the one whose `/mcp`
showed `gemdb` connected. Ask it something nobody wrote a query for.

> "What is the loss ratio by risk tier, and why is the High band cheaper to
> carry than Medium?"

It writes Python, runs it inside the database, and answers from the objects.

> "There is no query tool here. The surface is code-level: the agent writes
> Python and runs it in the database. What makes that work is that the objects
> know what they are — and `docs/dataset-for-agents.md` tells it what a
> policyholder *is*, because the MCP server knows how to talk to a database,
> not what is in this one."

`docs/mcp-questions.md` has nine questions with the exact answers a fresh book
returns, and `tools/refresh_mcp.py --verify` replays them over the real
transport. Say that; do not run it live.

**If the agent has no `gemdb` tools when you get here**, do not debug it in
front of the room. The beat survives without it, because the snippets the
document publishes are the same Python the agent would write. Keep this file
in the repository root, ready to run:

```python
# ask.py
import gemdb
from brainfreeze import analysis

book = gemdb.root["brainfreeze"]
print(analysis.loss_ratio_by_tier(book))
```

```sh
gemdb ask.py
```

```console
{'Medium': 0.729, 'High': 0.501, 'Low': 0.409}
```

**A file, not `gemdb -c`.** The one-liner answers `No module named
'brainfreeze'`, because `gemdb` puts the *script's* directory on the path and
`-c` has no script. The preamble published in `docs/mcp-questions.md` leaves
the path line out for the same reason: it is written for a notebook or a
`gemdb script.py`, both of which already have it.

You lose "it wrote the query itself" and you keep the point that matters: one
set of rules, and the same answer from a different way in. Fix the agent
afterwards — it started before the router did.

### 8 — Adding a field to a live database (3 min)

Switch to the `brainfreeze/model.py` tab and show the `Claim` class:

```python
class Claim:
    flavour = None
    toppings = ()
```

> "The claim form asks which flavour it was and what was on top. New claims
> carry both. The two thousand one hundred and seventy-two that came out of the
> CSVs read `None` and an empty tuple. Nothing was migrated. Nothing was
> rewritten. There was no downtime, because there was nothing to do."

**Then give the honest version, before anyone else does.**

> "And that works because those defaults were on the class before anything was
> committed. A claim written without them has no slot of its own, so it reads
> the default through the class. Adding a field *later* is a different story:
> editing a class compiles a different class, and instances already committed
> keep the one they were made under. So the claim is not 'edit the model and
> the database just knows'. It is that a schemaless object database lets you
> declare optional fields up front and pay nothing for them later. That is a
> claim about foresight, and it is true."

Volunteering this is worth more than surviving the question. It is also the
thing the room will remember you for.

### 9 — What it cost (2 min)

Close on `findings/`. Nine things that cost real time, each reduced to a script
that reproduces it on your own database rather than asking anyone to believe a
transcript.

> "Every one of these has a script you can run. The through-line is worth
> saying out loud: in most of them, the code that exists to report a problem is
> the code that breaks. Flask's logger cannot report an exception here, so a
> broken view closes the connection and says nothing at all."

If asked what is not solved: instance migration for a changed class shape.
That is Grail's §8.3, it is filed, and it is the one that decides whether this
is deployable for long-lived customer data.

---

## When it goes wrong

**The browser hangs on a page.** The first render of each template compiles it
into the database. Wait. If it is still hanging after a minute, see the next
one.

**A page returns nothing and the connection closes.** Flask's logging stub
cannot report an exception in a view, so this is what a broken handler looks
like. The traceback *is* in Terminal A. Look there, not at the browser.

**`No module named 'brainfreeze'`.** You ran a script from the wrong directory,
or from a subdirectory. `gemdb` puts the *script's* directory on the path, not
the working directory. Run from the repository root.

**A figure on screen disagrees with a figure in your notes.** The book has
drifted — a rehearsal bought a policy or filed a claim. `gemdb tools/seed.py`
and start again. The seed is the reset, and it takes nine seconds.

**The agent answers with a number you were not expecting.** Same cause. The
answers in `docs/mcp-questions.md` describe a *freshly seeded* book.

**`gemdb.mcp.enabled` is greyed out as an unknown setting.** Your build of the
extension does not declare it, and a stale duplicate install is the usual
reason — two folders under `~/.vscode-oss/extensions/` for the same version,
one platform-suffixed, only one of them registered. It does not matter for the
demo: `tools/refresh_mcp.py` serves the port either way, and the `lsof` check
in step 5 is the one that decides.

**The agent has no `gemdb` tools at all.** It started before the router was
listening. An HTTP MCP server is connected at session start, so a session that
came up without it never gets it — there is no retry and no error, just an
absence. Confirm the router with `lsof -nP -iTCP:50390 -sTCP:LISTEN`, then
quit the agent and start it again. Use the `ask.py` fallback in beat 7 if you
are already in front of people.

**Everything refuses to start, including `topaz`.** You have run out of
sessions. See below.

---

## The thing that will actually bite you

**The stone allows ten sessions and does not forgive running out.**

Every `gemdb` command takes one while it runs. The app holds one for as long
as it is up. The notebook kernel holds one. The MCP router holds one. A leaked
app — killed with the wrong signal, or closed with the window — can keep
holding one after you think it is gone, because `gemdb` is a shell wrapper and
killing the wrapper leaves the process it started.

Before you present, and after: check nothing is listening.

```sh
lsof -nP -iTCP:5000 -sTCP:LISTEN
```

Empty is what you want. If it is not, kill the whole process group rather than
the pid you can see.

Do not "just start a second app to check something". That is how the ten
become nine, and then eight.

---

## After

```sh
gemdb tools/seed.py          # leave a clean book for the next person
```

Stop the app. Check the port is free. The acceptance suite refuses to run while
something is listening on 5000, which is the same instinct.

If you want to prove the demo still works rather than remember that it did:

```sh
.venv-acceptance/bin/behave
```

Eight features, fifteen scenarios, in a real browser, ninety seconds. It drives
every journey above except the notebook narrative and leaves its screenshots
and payloads in `artifacts/`.
