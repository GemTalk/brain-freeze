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

**Terminal A will print nothing, ever.** No banner, no "Running on", no access
log, not even after it answers. Werkzeug writes all of that through `logging`,
which Grail stubs. A working app and a hung one look identical from the
outside, so do not read the silence as a problem — the `curl` above is how you
tell them apart.

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

**Do this.** Click [the app](http://127.0.0.1:5000/) in the table above. It
opens in Simple Browser, in a tab. Drag that tab to the right half of the
window so a terminal can sit beside it.

You are looking at a table of policy ids, plan, risk band, status, claims and
what each has been paid. The heading says **900 policyholders, live in the
database**.

**Do not explain the architecture yet.** The beat only works if they have first
decided this is an ordinary web app.

> "Brain freeze insurance. Mock company, real dataset — nine hundred
> policyholders, five thousand cold treats, two thousand claims."

Click any policy id to show a history, then click **All policyholders** to come
back. That is the whole tour.

### 2 — A claim, and the arithmetic behind it (4 min)

**Do this, in order.**

1. In the **Go to a policy** box, type `BF-100332` and click **Find**. It goes
   straight there, because one match does not need choosing. Clean history,
   Standard plan, nothing claimed yet.
2. Click **File a claim**.
3. Fill the form. Every question is a radio button except the pain score:

   | Question | Pick |
   | --- | --- |
   | What did they have? | slushie |
   | How cold was it? | Straight from the freezer |
   | How much of it? | A lot |
   | How fast? | All at once |
   | How bad was it? (0–10) | type `9` |
   | How long did it last? | Longer than ten |
   | Where did it hurt? | Forehead |
   | What did it feel like? | Stabbing |
   | Which flavour? | Mint choc chip |
   | Anything on top? | Sprinkles, Hot fudge |

4. Click **Send the claim**.

**The decision screen is the beat.** With those answers it reads
**"$55.00 is yours"**, and under it four lines. Point at them one at a time.

| Line | Figure | What it is |
| --- | --- | --- |
| What we worked it out at | `$99.00` | what that severity is worth |
| Trimmed to your $60.00 episode cap | `−$39.00` | the plan's per-episode limit |
| Your deductible | `−$5.00` | the excess |
| **Paid to you** | **`$55.00`** | the three above, resolved |

Those figures are exact for the answers in the table above. If you see
different ones, you picked a different option somewhere — which is fine in the
room, the arithmetic still adds up, but it means this page is no longer the one
you rehearsed.

> "Nobody typed an amount. The claimant described what happened — what they
> ate, how much, how fast, how much it hurt, how long — and the rules worked
> out what that is worth. The app did not do this arithmetic. It asked the
> same function the notebook and the agent will ask in a minute, and printed
> the answer."

Click **see the policy**. The claim is on the record, in date order, among
episodes dated later this year that have not happened yet.

**Then show a refusal**, because a demo that only ever pays is not an
insurance demo.

1. **All policyholders** → type `BF-100092` → **Find**. Its tile reads **3/4
   claims used**.
2. **File a claim**, answer it any way you like, **Send the claim**. It pays.
   Click **see the policy**: now **4/4**.
3. Click **File a claim** again. Before you type anything, a banner across the
   top of the form:

   > *This policy has used all 4 approvals for the year. A new claim is
   > refused until it renews.*

   Fill it in and send it anyway — that is the point. It comes back **Not this
   time**, and where the arithmetic was there is one sentence: *Exceeded annual
   claim limit*.

> "It did not apologise and it did not say 'error'. It named the rule that
> bound. That string is one of nine the rules can produce, and each one also
> carries an identifier a script can check without parsing English."

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

**Do this.** Click the `brain-freeze.ipynb` tab. Top right, the kernel picker
should already say **GemDB**; if it says *Select Kernel*, click it, choose
**Jupyter Kernel**, then **GemDB**.

> "No connection step. Picking the kernel *is* the connection — the kernel is a
> session on this database."

Run cells with `Shift+Enter`, one at a time, so people can read them. Do **not**
use Run All; the last cell is beat material and you want to arrive at it
deliberately.

| Cell | What to say while it runs |
| --- | --- |
| **1** the path | "The one thing it has to be told: where the code is. A kernel starts in the database's directory, not this one." It prints the repository it found. |
| **2** `import gemdb` | "One lookup. `gemdb.root` is the database's root namespace, and `book` is the same object the web app just served." |
| **3** `policy = book["BF-100539"]` | The one to stop on. See below. |
| **4** the map | "Four facts and a `for` loop. That is the whole query API, and it prints itself rather than being written down somewhere." |
| **5** `book_summary` | "Nine hundred policies, and the loss ratio for the whole book." |
| **7** loss ratio by band | Stop here too. See below. |
| **9**, **10** the chart | "No matplotlib. The kernel renders text, so a chart is ten lines you can read." |

Cell 1 is not ceremony and it is worth ten seconds: it is the same three lines
every script in `tools/` and `web/` opens with, for the same reason, and beat 9
has a finding about what happens when you try to share them.

**Stop on cell 3.** It prints:

```
class            : Policyholder from brainfreeze.model
answers to       : 33 public names
actually stored  : 15
```

> "Thirty-three names, fifteen of them stored. The rest are computed when you
> ask. `risk_tier` is not a column that could drift out of step with the data.
> It is a question the object answers — which is why there was no schema to
> change when we added flavours."

**Stop on cell 7.** `{'Medium': 0.729, 'High': 0.501, 'Low': 0.409}`.

> "Read that again. High is cheaper to carry than Medium. The 1.9x loading on
> the High band over-prices the risk, so the customers the underwriter is most
> worried about are the most profitable, and the middle of the book is where
> the money leaks. That is a real finding about this data, not a scripted one."

Leave cells 11 and 12 alone. They are the refresh beat, and they only say
anything when another session has committed in between — which is beat 6, and
it is better shown in the browser.

### 6 — The beat worth slowing down for (2 min)

**This is the demo.** If you only get one thing across, get this one.

**Do this.**

1. Click [BF-100184](http://127.0.0.1:5000/policies/BF-100184) to put it in the
   Simple Browser. Its status tag says **Active**. Say so out loud, and click
   **File a claim** to show the form opens normally. Go back.
2. In Terminal B, beside the browser:

   ```sh
   gemdb tools/lapse.py BF-100184
   ```

   It prints what it did and ends *"the running app sees this on its NEXT
   request — it takes a new view per request, so no restart is needed."*

   > "Different process. Different session. It does not know the web app
   > exists."

3. Refresh the Simple Browser — the circular arrow in its toolbar, or `Cmd+R`
   with it focused. **Do not restart anything.** The status tag now reads
   **Lapsed**, with a date.
4. Click **File a claim** again. The form is gone. In its place:

   > *Cover on this policy ended on 2026-09-15. Anything filed now is refused.*

   Refused before a word is typed, and it names which absence of cover it is
   rather than saying "error".

> "No restart. No reload. No cache to invalidate, no message queue, no polling.
> A session sees the database as of its last transaction boundary, so the app
> takes a new view before every request. That is the only reason this works,
> and it is four lines."

Put it back, so the next run starts where this one did:

```sh
gemdb tools/lapse.py BF-100184 --reinstate
```

### 7 — The agent (3 min)

**Do this.** Click into the Claude Code panel — the session you started in
step 5, the one whose `/mcp` showed `gemdb` connected. Type this, verbatim:

```
Using the gemdb tools, work out the loss ratio by risk tier for the
brainfreeze book, and tell me why the High band is cheaper to carry
than Medium.
```

Naming the tools is not superstition: without it the agent may go and read the
repository's source instead of asking the database, which answers the question
correctly and shows nothing. You want it calling `eval_python`.

Watch what it does, not just what it says. It writes Python, runs it **inside
the database**, and answers from the objects.

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

**Do this.** Click the `brainfreeze/model.py` tab and `Cmd+F` for `flavour`.
It lands on line 37. Show those two lines and nothing else:

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

If someone asks to *see* it fail, do not do it live — it needs two sessions and
a redeploy, and it is four minutes you do not have. Point at
`findings/03_class_identity.py`, which reproduces it in two runs on their own
database, and say the output is in the README under CUJ-4.

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

**The app "hangs" when you start it, with nothing in the log.** It is almost
certainly serving. `gemdb web/app.py` is a foreground server that never
returns to the prompt, and it prints nothing at any point because Werkzeug's
banner and access log both go through `logging`, which Grail stubs. Ask it
rather than watching it:

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/
```

`200` means it was working the whole time. Nothing on the port means it really
did fail, and the reason will be in the terminal — a genuine failure to start
does print, because it raises rather than logging.

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
