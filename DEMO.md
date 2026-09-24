# The demo, as a script

Twenty-eight minutes, nine beats, one argument: **there is one database,
several ways into it, and nothing in between.** No ORM, no schema, no
migration, no serialisation format, no connection string.

This is the presenter's copy. [`README.md`](README.md) is the walkthrough and
carries every command with its real output; this says what to *do*, in what
order, what to say while it happens, and what to do when it goes wrong.

The spine is one policy. The room watches it get quoted, bought, claimed
against, lapsed and explained, and never has to hold a second identifier in
their head.

**If you only have twenty minutes,** drop beat 7 (the live field) and beat 8
(the agent). That leaves 22 and the argument still closes, because beat 5
already makes the schema point and beat 9 tells them where the rest is. Do not
drop beat 3 to save time — a demo that never pays a claim is not an insurance
demo, and the arithmetic is what makes beat 5's "the class is the schema" land
as a consequence rather than a slogan.

Read "The three traps" before you stand up.

---

## Before the room

Ten minutes before, not one. The first render compiles templates into the
database and is the slowest thing in the demo; you do not want an audience
watching it.

```sh
export PATH="$HOME/GemDB/bin:$PATH"     # not needed in a VSCodium terminal
cd ~/GemTalk/brain-freeze
```

**1. Check the database can run a web framework.** If this fails, nothing else
will, and the error will not tell you why.

```sh
gemdb -c 'import re; print("re works:", bool(re.match(r"a+", "aaa")))'
```

Anything other than `re works: True` — stop and see "Before you start" in the
README. It is one assignment, not a reinstall.

**2. Seed a clean book.** Nine seconds. Do this even if you seeded yesterday:
a rehearsal leaves quotes given, policies bought and claims filed, and beats 2
and 3 both depend on the book being untouched.

```sh
gemdb tools/seed.py
```

Last line should be `Replaced gemdb.root["brainfreeze"]. Committed.`

**3. Confirm the book is clean.** Ten seconds, and it tells you the two
identifiers the demo is about to mint.

```sh
gemdb -c 'import gemdb; b = gemdb.root["brainfreeze"]; print(len(b), "policies,", len(b.quotes), "quotes")'
```

`900 policies, 0 quotes`. If the quote count is not zero, seed again — you are
looking at yesterday's rehearsal, and the ids below will be wrong.

**4. Start the app and warm it.**

```sh
gemdb web/app.py
```

**A working server prints nothing.** Silence is success. In another terminal:

```sh
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/
```

`200`. **Do not skip this.** The warm-up is not superstition: the first
request is the slow one, and until the app has answered once it is carrying
its whole startup as uncommitted work.

**5. Open the notebook and pick the kernel now,** so the room never watches a
kernel start. Open `brain-freeze.ipynb`, set the kernel to **GemDB**, and run
code cells 1 and 2 only. Leave it there.

**6. Check the agent can reach the database,** if you are doing beat 8. In the
Claude Code panel, `/mcp` should show `gemdb` connected. If it does not, see
"When it goes wrong" — there is a known packaging bug with a one-line fix, and
you do not want to meet it in front of the room.

---

## The run of show

Times are what the beat takes when it goes well. Cell numbers below count
**code cells only** — markdown cells are not numbered, because Jupyter does not
number anything on screen and counting the prose is how a presenter ends up two
cells adrift.

### 1 — An insurance company (1 min)

**Do this.** Open <http://127.0.0.1:5000/> in Simple Browser and drag the tab
to the right half of the window so a terminal can sit beside it.

A table of policy ids, plan, risk band, status, claims and what each has been
paid. The heading says **900 policyholders, live in the database**.

**Do not explain the architecture yet.** The beat only works if they have
first decided this is an ordinary web app.

> "Brain freeze insurance. Mock company, real dataset — nine hundred
> policyholders, five thousand cold treats, two thousand claims."

### 2 — A quote, and the policy it becomes (5 min)

The web flow, start to finish. This is the beat that gives you the policy the
rest of the demo uses.

**Do this, in order.**

1. Click **Get a quote**. Five questions, nothing else.

2. Answer them exactly like this — the figures below are what the room will
   see, so use these answers and not your own:

   | Question | Pick |
   | --- | --- |
   | How old? | `9` |
   | Migraine diagnosis? | No |
   | Tension-type headaches? | No |
   | How fast do they eat it? | Very fast |
   | Favourite cold treat? | Slushie |

3. Click **See the price**. **Stop and look at the address bar.** It says `/quote/QTE-000001`.

   > "That is not a result page. That is an address. The quote is an object,
   > it has an id, and it is in the database — not in a session, not in a
   > hidden field, not in a cookie."

   The score is **85.0, High**, built from four rows: everyone starts at 45,
   +18.0 for eating fast, +10.0 for being 9, +12.0 for slushies. Three plans
   priced off it:

   | Plan | A year | A month | Limit | Deductible |
   | --- | --- | --- | --- | --- |
   | Basic | $85.50 | $7.13 | $25.00 | $10.00 |
   | Standard | $171.00 | $14.25 | $60.00 | $5.00 |
   | Premium | $342.00 | $28.50 | $150.00 | $0.00 |

4. **Reload the page.** Nothing is re-asked and nothing is re-computed.

   > "Refreshing a result page normally either re-posts the form or loses it.
   > This just re-opens the object."

5. Click **Take out Standard**. You land on `/policies/BF-100900`, a policy
   that did not exist ninety seconds ago, at **$171.00** — the number they
   were shown.

   > "It was sold at the price the quote showed. Not re-priced at checkout —
   > the price was *stored*, because a quote is a promise made on a date."

6. Go **back to the quote**, `/quote/QTE-000001`. It now names the policy it
   became.

   > "The quote remembers what it turned into, so it cannot be sold twice."

7. Click **All policyholders**. The heading now reads **901**.

**One sentence on the JSON, and do not open a terminal for it:**

> "Everything you just saw is also six JSON endpoints — same objects, and the
> five questions come out of the model rather than being written down twice,
> so the form and the API cannot drift apart."

### 3 — A claim, and the arithmetic behind it (4 min)

A policy nobody has claimed on, so the decision screen is the only thing on it.

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

### 4 — The reveal (1 min)

Switch to the terminal running the app and show what is running.

```
gemdb web/app.py
```

> "That is the whole command. There is no connection string in this repository
> — grep for one. There is no driver, no pool, no ORM. The web app is running
> *inside* the database, and `gemdb.root` is the root namespace. The policy you
> just sold and the claim you just paid are objects, not rows."

This is the pivot. Everything after it is the same objects from a different
angle.

### 5 — The notebook (7 min)

The beat carrying the argument. Four moves, in this order. **The order is not
arbitrary** — see the second trap.

Run cells with `Shift+Enter`, one at a time. Do **not** use Run All. Cells 1
and 2 are already run from "Before the room".

| Cell | What to say |
| --- | --- |
| **1** | already run — puts the repository on `sys.path` so the model is found on disk |
| **2** | already run — `gemdb.root["brainfreeze"]` is the book, and it echoes itself |
| **3** | Move 1: `dir(policy)` and `vars(policy)` on `BF-100539` |
| **9** | defines `bar_chart` — needed by Move 3, and the thing `abort()` would destroy |
| **11** | Move 2: the counts, before the new view |
| **12** | Move 2: commit, then refresh, then the counts again |

**Leave cells 11 and 12 alone** until Move 2 — running them early spends the
beat, because once this session has taken the new view there is nothing left
to be surprised by.

**Move 1 — there is no schema to introspect** (cell 3, ~1 min)

`dir(policy)` gives 30-odd public names. `vars(policy)` gives about half of
them. The rest are computed from the class on the way out.

> "Half of what a policy knows about itself is stored. The other half is
> worked out from the rules, every time you ask. There is no table here, no
> column list, and nothing to migrate — **the class is the schema**."

**Move 2 — what you just did is in here** (cells 11 and 12, ~2 min)

Run cell 11 first. It still says **900 policies**, and the event count has not
moved either.

> "The app committed a new policy and a paid claim in the last few minutes and
> this session cannot see either. Every notebook, the web app and each MCP
> client gets its own session and its own view. That is not a bug, it is the
> isolation you are paying for."

Then cell 12 — `gemdb.commit()` then `gemdb.refresh()`.

> "Commit first, to keep this session's compiled cells. Then take the new
> view."

Now it says **901**, the events have moved, and `bar_chart` is still defined.
Then type this one yourself — it is not a cell:

```python
book.quotes["QTE-000001"]
```

```
<SavedQuote QTE-000001 High $171.00 -> BF-100900>
```

> "One line, and the object tells its own story: which quote, what band, what
> it cost, and what it became. No export, no reload, no serialisation format."

**Move 3 — change a rule, and nine hundred answers change** (~2 min)

This is the demo. Slow down. Type these; they are not cells.

```python
from brainfreeze import underwriting

def bands():
    t = {}
    for p in book:
        t[p.risk_tier] = t.get(p.risk_tier, 0) + 1
    return tuple(t.get(k, 0) for k in ("Low", "Medium", "High"))

bands()
```

```
(137, 497, 266)
```

Then one assignment:

```python
underwriting.MIGRAINE_POINTS = 40.0
bands()
```

```
(135, 478, 287)
```

> "I changed what a migraine diagnosis is worth. Twenty-one policies just
> moved up into the High band. There was no `UPDATE`, no migration, no
> reindex and no downtime — because there was nothing stored to update. The
> score was never a column. It is a property on the class, and the class is
> live code in the database."

Re-run cell 9's chart if you want it on screen. The histogram moves.

**Move 4 — but the policy you sold does not move** (~2 min)

```python
book.quotes["QTE-000001"].plans["Standard"]["annual"]
```

Still `$171.00`.

> "Same system, opposite choice. The score is derived on purpose, so changing
> a rule moves it. The quote's prices are *stored* on purpose, so a customer
> is sold what they were shown. Both of those are one decision, written in
> ordinary Python, visible in the class — and that is the other half of what
> 'the class is the schema' means. You choose what is kept and what is worked
> out, per class, and you can read the choice."

**Then put it back, and say why.**

```python
underwriting.MIGRAINE_POINTS = 22.0
```

> "And that was a transaction. Nothing left this session — the app next door
> still bands the book the old way, and nothing was committed. A schema change
> you can roll back."

### 6 — Someone else moves the book (2 min)

**Do this.** Put `BF-100900` — the policy they watched get sold — in the
Simple Browser. Its status says **Active**. Click **File a claim** to show the
form opens normally, then go back.

In a terminal beside the browser:

```sh
gemdb tools/lapse.py BF-100900
```

> "Different process. Different session. It does not know the web app exists."

Reload the browser. The policy is lapsed, and filing a claim is now refused
with a sentence naming the date: *Cover on this policy ended on* — and then the
date.

> "The running app saw that on its next request. It takes a new view per
> request, so there is no restart and no cache to bust."

### 7 — Adding a field to a live database (3 min)

**Do this.** Click the `brainfreeze/model.py` tab and `Cmd+F` for `flavour`.
It lands on line 37. Show those two lines and nothing else:

```python
class Claim:
    flavour = None
    toppings = ()
```

> "The claim form asks which flavour it was and what was on top. The claim you
> filed in beat 3 carries both — mint choc chip, sprinkles and hot fudge. The
> two thousand one hundred and seventy-two that came out of the CSVs read
> `None` and an empty tuple. Nothing was migrated. Nothing was rewritten.
> There was no downtime, because there was nothing to do."

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
[`findings/03_class_identity.py`](findings/03_class_identity.py), which
reproduces it in two runs on their own database, and say the output is in the
README under CUJ-4.

### 8 — The agent (3 min)

**Do this.** Click into the Claude Code panel — the session whose `/mcp` shows
`gemdb` connected. Type this, verbatim:

```
Using the gemdb tools, work out the loss ratio by risk tier for the
brainfreeze book, and tell me why the High band is cheaper to carry
than Medium.
```

Naming the tools is not superstition: without it the agent may read the
repository's source instead of asking the database, which answers the question
correctly and shows nothing. You want it calling `eval_python`.

It should land on **Low 0.431, Medium 0.729, High 0.501**.

> "The 1.9x loading on the High band over-prices the risk it is pricing for.
> The customers the underwriter is most worried about are the most profitable,
> and the middle of the book is where the money leaks. That is a real finding
> about this dataset, and the agent got it from the same objects the web app
> serves — not from a copy, not from an export."

### 9 — What it cost (2 min)

Close on [`findings/`](findings/). Nine things that cost real time, each
reduced to a script that reproduces it on your own database rather than asking
anyone to believe a transcript.

> "Every one of these has a script you can run. The through-line is worth
> saying out loud: in most of them, the code that exists to report a problem
> is the code that breaks."

---

## The three traps

### The notebook's commit can stop the app answering

Move 2 of beat 5 runs `gemdb.commit()`. If this session and the app have both
*called* the same function -- and `len(book)` alone is enough -- that commit
takes the object the app is still holding uncommitted, and the app's next
request meets a Write-Write conflict it cannot recover from. It does not slow
down or return an error. It stops answering, and stays stopped, with nothing
useful in its terminal (findings 7 and 10).

Beat 6 needs the app. **So after Move 2, before you move on, reload the
browser.** If the page comes back, carry on. If it hangs, the app is gone:

```sh
gemdb web/app.py                                          # restart it
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/   # warm it
```

That is thirty seconds of dead air, which is why you check during the beat
rather than discovering it in front of the lapse. `gemdb findings/10_shared_session_state.py`
reproduces it deliberately if you want to see it once before you meet it.

### `abort()` is not your undo

`gemdb.abort()` does revert the weight from Move 3. It also **silently
discards every function you defined in that session**, because Grail compiled
them into the database as uncommitted work. It does not raise:

```
>>> gemdb.abort()
>>> bands()
<UndefinedObject object at 0x101>
```

Not a `NameError` — a wrong answer. In the notebook that means `bar_chart` and
every helper from earlier cells quietly evaporates and the next cell shows you
garbage.

**The undo is assignment.** Set `MIGRAINE_POINTS` back to `22.0`. Verified:
the bands return to `(137, 497, 266)` and every function survives.

Related: `gemdb.needs_commit()` is `True` from the moment you run *any* code,
before you have touched a single weight. It is not a signal that you changed
data, and it will alarm you at exactly the wrong moment if you do not know
that.

### The stone allows ten sessions and does not forgive running out

Every `gemdb` command takes one while it runs. The app holds one for as long
as it is up. The notebook kernel holds one. The MCP router holds one. A leaked
app — killed with the wrong signal, or closed with the window — can keep
holding one after you think it is gone, because `gemdb` is a shell wrapper and
killing the wrapper leaves the process it started.

Before you present, and after:

```sh
lsof -nP -iTCP:5000 -sTCP:LISTEN
```

Empty is what you want. If it is not, kill the whole process group rather than
the pid you can see.

Do not "just start a second app to check something". That is how the ten
become nine, and then eight. It is also how you end up with two servers where
one of them is a corpse holding the port, which looks exactly like a hang.

---

## When it goes wrong

**The quote page 400s.** A value the form should not have been able to send.
The message names the field. Re-seed and try again with the answers above.

**The bought policy is not `BF-100900`.** The book was not clean. The id is
used again in beat 6, and the quote id in beat 5's Move 2 will have moved with
it, so write down what you actually got before carrying on. Re-seed before the
next run.

**The decision screen shows figures other than $99.00 / $39.00 / $5.00 /
$55.00.** You picked a different option somewhere in the claim form. The
arithmetic is still right and the beat still works — say the numbers you see,
not the ones written here.

**Cell 12 raises `PendingChangesError`.** You called `refresh()` without
committing first. Run `gemdb.commit()`, then `gemdb.refresh()`.

**The notebook shows 900 after cell 12.** The app had not committed yet.
Reload the browser, then re-run cell 12.

**`/mcp` does not show `gemdb` connected.** Known bug, and it is not your
setup: the payload GemDB assembles omits `session-lifetime.sh`, which
`run-server.sh` sources unconditionally, so the server exits immediately with
`./session-lifetime.sh: No such file or directory`. Copy that one file into the
payload directory by hand and restart the server. Tracked as issue #65. If you
cannot get it up in the ten minutes before the room, drop beat 8 — it is the
one beat with no dependency on any other.

**The app stopped answering after the notebook.** Not a coincidence and not
your laptop -- see the first trap. Restart it and warm it; nothing in the book
was lost, because the conflict is over compiled code rather than data.

**The agent reads source files instead of querying.** You left "Using the
gemdb tools" off the front. Say it again with the phrase.

---

## After

```sh
gemdb tools/seed.py          # leave a clean book for the next person
lsof -nP -iTCP:5000 -sTCP:LISTEN   # and leave no sessions behind
```
