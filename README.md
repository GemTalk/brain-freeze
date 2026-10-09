# Brain Freeze Insurance

A GemDB tutorial. You will build on a small insurance company — it covers
ice-cream headaches — and along the way see what GemDB is for:

- **Python runs inside the database.** Your classes, your rules, a Flask app.
- **Persistence is built in.** No tables, no ORM, no mapping layer.
- **Schema changes are easy.** Add a field to a class full of live data, and
  the data comes along.
- **Every tool sees the same objects.** The app, a notebook and an AI agent,
  all at once.

It takes about half an hour.

## Before you start

Install [GemDB Code](https://github.com/GemTalk/GemDB_Code) in VS Code and
follow its setup; it creates your database and puts `gemdb` on your terminal's
path. Then:

```sh
git clone https://github.com/GemTalk/brain-freeze
cd brain-freeze
```

Every command below runs from this directory, in a VS Code terminal.

---

## 1. Load data

```sh
gemdb tools/seed.py
```

```console
Wrote gemdb.root["brainfreeze"]. Committed.
```

That is 900 policyholders and 2,172 claims, read from `data/*.csv` and stored
as ordinary Python objects — the classes in
[`brainfreeze/model.py`](brainfreeze/model.py). Ask for one back:

```sh
gemdb -c 'import gemdb; p = gemdb.root["brainfreeze"]["BF-100539"]; print(p.plan_name, p.total_paid)'
```

```console
Sundae 179.97
```

There is no schema file and no save method. `gemdb.root` is a dictionary that
persists, and `gemdb.commit()` is the only call that writes.

The loader is ordinary Python: the standard `csv` module, the model's
classes, and those two. Trimmed from [`tools/seed.py`](tools/seed.py):

```python
book = Book()
with open("data/policyholders.csv", newline="") as handle:
    for row in csv.DictReader(handle):
        book.add(Policyholder(
            policy_id=row["policy_id"],
            age=int(row["age"]),
            plan_name=row["coverage_plan"],
            ...
        ))

gemdb.root["brainfreeze"] = book
gemdb.commit()
```

## 2. Launch the web app

```sh
gemdb web/app.py
```

Open <http://127.0.0.1:5050/>.

Start a quote from the home page: answer five questions, pick one of three
prices, and the policy you bought comes back as its ID card. File a claim
against it: say how bad it was and how long it lasted, and the rules decide
what it pays. Every policyholder is under **Policies** and every claim under
**Claims**.

Now stop the app (Ctrl-C) and start it again. The policy you bought and the
claim you filed are still there. Nothing was saved, because nothing needed to
be.

The app is plain Flask, and the insurance rules are plain Python. They run
where the data lives, so there is no query layer between them.

## 3. Change the schema

Claims should record *which* ice cream did it. Leave the app running.

In [`brainfreeze/model.py`](brainfreeze/model.py), give `Claim` two fields:

```python
class Claim:
    flavour = None
    toppings = ()
```

Then show them in the app: the choices go in [`web/forms.py`](web/forms.py),
the two questions in
[`web/templates/claim_form.html`](web/templates/claim_form.html) and the line
on the claim page in [`web/templates/decision.html`](web/templates/decision.html),
and the answers into the new `Claim` where
[`web/routes_html.py`](web/routes_html.py) files it.

Now load what you changed into the database:

```sh
gemdb tools/load.py
```

```console
Reload the page: the running app serves what you loaded.
```

Reload your browser. The form asks the new questions, and a claim you file now
records the answers. Open any of the 2,172 claims filed before you started:
they still load, and read as no flavour and no toppings.

No migration, no reseed, and the app never stopped: loading is the deploy. The
2,172 old claims were committed as instances of `Claim`, they are still
instances of `Claim`, and `Claim` now has the new fields.

## 4. Jupyter

Open [`brain-freeze.ipynb`](brain-freeze.ipynb) in VS Code and run the cells.

The notebook works on the same objects as the app: loss ratio by risk tier,
what an approved claim is worth, where the payouts cluster. No export, no
connection string.

Keep it open, buy a policy in the browser, and run the policy-count cell again.
It has not changed: the notebook sees the database as of its last transaction,
so an analysis does not shift under you halfway through. Click **↻ Refresh
Notebook View** in the notebook's toolbar, or run

```python
gemdb.refresh()
```

and run the cell again. Now it has.

(The toolbar button arrives once
[GemTalk/GemDB_Code#97](https://github.com/GemTalk/GemDB_Code/pull/97) is
merged and released; until then, `gemdb.refresh()` is the way.)

## 5. MCP

GemDB's MCP server is off until you turn it on. From the GemDB Code sidebar's
**⋯** menu, choose **Connect an AI Agent to GemDB**: choose **Turn It On**, then
**Claude Code**, and GemDB connects Claude Code to this folder. Start a new
Claude Code conversation here, and ask:

> Which plan is losing money?

The agent answers by running Python against the live book: the same objects,
through the same `brainfreeze` code. It needs no export, no API and no
description of your schema.

Ask it to make the change from step 3 for you, and watch it edit the class, the
form and the page — while the app keeps serving.

---

## What is in here

```
brainfreeze/         the model and the rules
web/                 the web app
tools/               seed.py, and the other commands above
data/                the sample book, as CSV, and generate.py, which made it
brain-freeze.ipynb   the notebook
BRANDING.md          how the web app's look is put together, and how to
                     make it your own (agents: the rebrand skill)
.claude/skills/      what an agent knows how to do here: rebrand the app,
                     and change the schema (schema-evolution)
```
