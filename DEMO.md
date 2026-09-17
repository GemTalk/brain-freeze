# The demo, as a script

Twenty minutes, seven beats, one argument: **there is one database, several
ways into it, and nothing in between.** No ORM, no schema, no migration, no
serialisation format, no connection string.

This is the presenter's copy. [`README.md`](README.md) is the walkthrough and
carries every command with its real output; this says what to *do*, in what
order, what to say while it happens, and what to do when it goes wrong.

The spine is one policy. The room watches it get quoted, bought, lapsed and
explained, and never has to hold a second identifier in their head.

Read "The two traps" before you stand up.

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

**2. Seed a clean book.** Nine seconds. Do this even if you seeded yesterday:
a rehearsal leaves quotes given and policies bought, and beat 2 depends on the
book being untouched.

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
cell 1 and cell 2 only. Leave it there.

---

## The run of show

Times are what the beat takes when it goes well. The whole thing is twenty
minutes and there is slack in it.

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

### 3 — The reveal (1 min)

Switch to the terminal running the app and show what is running.

```
gemdb web/app.py
```

> "That is the whole command. There is no connection string in this repository
> — grep for one. There is no driver, no pool, no ORM. The web app is running
> *inside* the database, and `gemdb.root` is the root namespace. The policy you
> just sold is an object, not a row."

This is the pivot. Everything after it is the same objects from a different
angle.

### 4 — The notebook (8 min)

The longest beat and the one carrying the argument. Four moves, in this order.
**The order is not arbitrary** — see the second trap.

Run cells with `Shift+Enter`, one at a time. Do **not** use Run All.

**Move 1 — there is no schema to introspect** (cells 4–5, ~1 min)

`dir(policy)` gives 30-odd public names. `vars(policy)` gives about half of
them. The rest are computed from the class on the way out.

> "Half of what a policy knows about itself is stored. The other half is
> worked out from the rules, every time you ask. There is no table here, no
> column list, and nothing to migrate — **the class is the schema**."

**Move 2 — the policy you just sold is in here** (cells 18–21, ~2 min)

Run cell 19 first. It still says **900**.

> "The app committed a new policy two minutes ago and this session cannot see
> it. Every notebook, the web app and each MCP client gets its own session and
> its own view. That is not a bug, it is the isolation you are paying for."

Then cell 21 — `gemdb.commit()` then `gemdb.refresh()`.

> "Commit first, to keep this session's compiled cells. Then take the new
> view."

Now it says **901**. Then:

```python
book.quotes["QTE-000001"]
```

```
<SavedQuote QTE-000001 High $171.00 -> BF-100900>
```

> "One line, and the object tells its own story: which quote, what band, what
> it cost, and what it became. No export, no reload, no serialisation format."

**Move 3 — change a rule, and nine hundred answers change** (~3 min)

This is the demo. Slow down.

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

Re-run the bar chart cell if you want it on screen. The histogram moves.

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

### 5 — Someone else moves the book (2 min)

**Do this.** Put `BF-100900` — the policy they watched get sold — in the
Simple Browser. Its status says **Active**. Click **File a claim** to show the
form opens normally, then go back.

In a terminal beside the browser:

```sh
gemdb tools/lapse.py BF-100900
```

> "Different process. Different session. It does not know the web app exists."

Reload the browser. The policy is lapsed, and filing a claim is now refused
with a sentence naming the date.

> "The running app saw that on its next request. It takes a new view per
> request, so there is no restart and no cache to bust."

### 6 — The agent (3 min)

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

### 7 — What it cost (2 min)

Close on [`findings/`](findings/). Nine things that cost real time, each
reduced to a script that reproduces it on your own database rather than asking
anyone to believe a transcript.

> "Every one of these has a script you can run. The through-line is worth
> saying out loud: in most of them, the code that exists to report a problem
> is the code that breaks."

If asked what is *not* solved: say that adding a field to a class with
committed instances used to strand every one of those records — `isinstance`
answered `False` — and that this was fixed in Grail rather than worked around
here. `tests/test_class_identity.py` measures it either side of the upgrade.

---

## The two traps

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
become nine, and then eight.

---

## When it goes wrong

**The quote page 400s.** A value the form should not have been able to send.
The message names the field. Re-seed and try again with the answers above.

**The bought policy is not `BF-100900`.** The book was not clean. Finish the
beat with whatever id you got — nothing downstream cares except your script.
Re-seed before the next run.

**Cell 21 raises `PendingChangesError`.** You called `refresh()` without
committing first. Run `gemdb.commit()`, then `gemdb.refresh()`.

**The notebook shows 900 after cell 21.** The app had not committed yet.
Reload the browser, then re-run cell 21.

**The agent reads source files instead of querying.** You left "Using the
gemdb tools" off the front. Say it again with the phrase.

---

## After

```sh
gemdb tools/seed.py          # leave a clean book for the next person
lsof -nP -iTCP:5000 -sTCP:LISTEN   # and leave no sessions behind
```
