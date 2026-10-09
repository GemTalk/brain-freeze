# Brain Freeze Insurance

Brain Freeze is a demo app for a fictional insurer that offers friendly coverage for cold-stimulus headaches. It runs on GemDB, which supplies the Python environment and a persistent, object-oriented database. The database stores the data for quotes, policies, and claims, such as each policyholder's age, plan, and premium, and each claim's amount and decision.

<!-- TODO: short "what's in this repo" paragraph (per Sandeep): dataset generator/loader, the brainfreeze data model, and the web app. Write once those pieces have been walked through. -->

Brain Freeze is a demo, not real insurance.

**Note:** Found this repo on GitHub? To run the demo, install [GemDB Code](https://marketplace.visualstudio.com/items?itemName=GemTalkSystems.gemdb) and choose **Install Brain Freeze Demo** from its Getting Started page.

---

## Before you start

These steps set up the Brain Freeze demo in VS Code, using the GemDB Code extension. GemDB Code installs the database and the demo for you.

1. In VS Code, install **GemDB Code** and follow its Getting Started steps. Wait until the GemDB panel shows **Database: ready**.
2. From the same Getting Started page, choose **Install Brain Freeze Demo**. GemDB Code clones this repo into `~/GemDB/brain-freeze` and opens it in VS Code.
3. VS Code opens the folder in **Restricted Mode**. Click **Manage** in the banner, click **Trust**, and then close the **Workspace Trust** tab.
4. Open a terminal: **Terminal → New Terminal**, or press **Ctrl+`**. (On a narrow window, the Terminal menu is under **…**.)

Every command below runs in a VS Code terminal, from the `brain-freeze` folder. `gemdb` is a command-line tool: it runs a Python script inside the database.

---

## Load the demo data

In this step, you run `gemdb` commands in the terminal to load the demo data into the database and read some of it back.

```sh
gemdb tools/seed.py
```

This takes a few seconds. It reads `data/*.csv` and stores 900 policyholders and 4,993 cold-treat events as ordinary Python objects (the classes in `brainfreeze/model.py`). It ends with a summary that includes these lines:

```console
Loaded 900 policyholders and 4993 cold-treat events.
Wrote gemdb.root["brainfreeze"]. Committed.
```

In the **GemDB Code** panel, click refresh on **Persisted Objects**. `brainfreeze` now appears next to `greeting`. That is your data, stored in the database.

Ask for one policy back:

```sh
gemdb -c 'import gemdb; p = gemdb.root["brainfreeze"]["BF-100539"]; print(p.plan_name, p.total_paid)'
```

The command reads policy BF-100539 from the database and prints its plan and the total paid on its claims:

```console
Sundae 179.97
```

In a relational database, you define tables before you can store anything, and you convert your objects to rows and back. GemDB has no separate schema: the classes in `brainfreeze/model.py` define the data, and the database stores their instances as they are. `gemdb.root` is a dictionary that persists. Anything you store in it, or reach from it, becomes part of the database.

Changes stay private to your session until you call `gemdb.commit()`. A commit saves them permanently and makes them visible to other sessions, such as the web app and the notebook. If your session ends before you commit, GemDB discards the changes. `tools/seed.py` commits for you, which is why its output ends with `Committed.`

---

## Launch the web app

```sh
gemdb web/app.py
```

```console
Brain Freeze Insurance is running.

  Open:  http://127.0.0.1:5050/
```

Leave this terminal running. To see the website that Brain Freeze customers use to get a quote, buy a policy, and file a claim, open <http://127.0.0.1:5050/> in a web browser on the same computer.

Buy a policy:

1. Click **Start a quote**.
2. Answer the five questions, and click **See my prices**.
3. Choose a plan, for example **Choose Sundae**. Brain Freeze shows the new policy's ID card, with its policy number (for example, `BF-100900`).

File a claim against it:

1. On the ID card, click **File a claim**.
2. Answer the questions, and click **Send the claim**. The decision page shows what the claim pays.

Every policyholder is listed under **Policies**, and every claim under **Claims**. As each page loads, the app's terminal lists the request.

The app is built with Flask, a popular Python web framework, and the insurance rules are ordinary Python code. Both run inside the database, next to the data. Each quote, policy, and claim is a Python object, and the app reads and changes those objects directly, without an object-relational mapper (ORM) or SQL queries.

<!-- TODO: the "stop the app and start it again" persistence check. On GemDB Code 1.5.4, Ctrl+C drops to a `topaz 1>` prompt instead of stopping the app (brain-freeze tests/test_ctrl_c.py). Users must not see topaz. Waiting on Steven / GemDB Code for a clean way to stop the app. -->

---

## Change the schema with code, not with a table update

To improve the app, make each claim record the flavor of ice cream and the toppings that caused the brain freeze. In this step, you add two fields, `flavour` and `toppings`, to the `Claim` class and two questions to the claim form, while the app keeps running.

To keep the app running in its existing terminal, open a second terminal for this step: click **+** in the Terminal panel, or press **Ctrl+Shift+`**.

Use the VS Code editor to make the following edits to the app's Python files and page templates, and then save each file (**Ctrl+S**). To find each spot, search the file (**Ctrl+F**) for the line named in each edit. Keep the indentation shown in each edit, because Python uses indentation to structure code.

**a. [`brainfreeze/model.py`](brainfreeze/model.py)** (three changes in the `Claim` class)

Below the line `"""A claim filed against one cold-treat event."""`, add:

```python
    flavour = None
    toppings = ()
```

In `def __init__(...)`, change `rule=None):` to:

```python
                 flavour=None, toppings=None, rule=None):
```

Below the lines `if rule is not None:` and `self.rule = rule`, add:

```python
        if flavour is not None:
            self.flavour = flavour
        if toppings is not None:
            self.toppings = tuple(toppings)
```

**b. [`web/forms.py`](web/forms.py)**

Below the line that starts `PAIN_QUALITIES = [`, add:

```python
FLAVOURS = ["Vanilla", "Chocolate", "Strawberry", "Mint choc chip",
            "Cookie dough", "Something else"]
TOPPINGS = ["Sprinkles", "Hot fudge", "Whipped cream", "Nuts", "Cherry"]
```

**c. [`web/routes_html.py`](web/routes_html.py)** (two changes)

In `claim_form`, change `qualities=forms.PAIN_QUALITIES,` to:

```python
        qualities=forms.PAIN_QUALITIES, flavours=forms.FLAVOURS, toppings=forms.TOPPINGS,
```

In `file_claim`, change `rule=decision.rule)` to:

```python
        rule=decision.rule,
        flavour=request.form.get("flavour") or None,
        toppings=request.form.getlist("toppings") or None)
```

**d. [`web/templates/claim_form.html`](web/templates/claim_form.html)**

After the `</div></fieldset>` that closes the `qualities` choices, add:

```html
    <fieldset><legend>Which flavour?</legend>
      <div class="chips">{% for f in flavours %}
        {{ ui.chip('flavour', f, f, loop.first) }}{% endfor %}
      </div></fieldset>
    <fieldset><legend>Anything on top?</legend>
      <div class="chips">{% for top in toppings %}
        <label class="chip"><input type="checkbox" name="toppings" value="{{ top }}"><span>{{ top }}</span></label>{% endfor %}
      </div></fieldset>
```

**e. [`web/templates/decision.html`](web/templates/decision.html)**

After the line `<p class="sub num">{{ c.claim_id }} &middot; {{ e.trigger }}`, add:

```html
    {%- if c.flavour %} ({{ c.flavour }}{% if c.toppings %},
      {{ c.toppings|join(', ')|lower }}{% endif %}){% endif %}
```

Now load your changes into the database. In the second terminal, run:

```sh
gemdb tools/load.py
```

```console
Reload the page: the running app serves what you loaded.
```

Check the result in your browser:

1. Reload the page. Open any policy under **Policies**, and click **File a claim**. The form now asks **Which flavour?** and **Anything on top?**
2. Choose a flavor and one or more toppings, and click **Send the claim**. The decision page shows them after the claim number, for example `ice cream (Mint choc chip, hot fudge, whipped cream)`.
3. Click **Browse all claims**, and open a claim dated before today. It loads as before, with no flavor or toppings shown.

You did not migrate any data, reload the book, or restart the app. `gemdb tools/load.py` loaded your changes into the database, and the running app used them on its next request. The 2,172 older claims are still instances of `Claim`, and they read the new fields' default values (`None` and `()`), so they show no flavor or toppings.

If a page shows **Something went wrong. The terminal running this app has the traceback**, look at the app's terminal for the error. Usually a file is not saved or an edit is missing. Fix the file, save it, and run `gemdb tools/load.py` again.

---

## Explore the data in a Jupyter notebook

In this step, you open a Jupyter notebook that works with the same objects as the web app. Leave the app running in its terminal.

1. In the Explorer, open `brain-freeze.ipynb`.
2. Check the kernel at the top right of the notebook. VS Code selects **GemDB (Python in the database)** for you. If VS Code prompts you to choose a kernel, choose that one.
3. Click **Run All**.

The notebook runs inside the database, so the policies and claims you loaded are already there, with no export or connection string. Its cells show a summary of the book, the loss ratio by risk band, what an approved claim is worth, and where the payouts cluster.

### See another session's changes

The notebook and the web app are separate sessions. Each session sees the database as of its last transaction, so an analysis does not change partway through while other sessions commit. The last section of the notebook, **Seeing another session's commit**, shows this:

1. Scroll to that section. After **Run All**, the cell that starts `print("policies:"` shows how many policies the notebook sees, for example `policies: 901`. Note the number.
2. In your browser, buy another policy: click **Start a quote**, answer the questions, click **See my prices**, and choose a plan.
3. In the notebook, run only the `policies:` cell: click ▷ to the left of the cell, or click in the cell and press **Ctrl+Enter**. Do not click **Run All**. The number has not changed, because the notebook still sees the database as it was.
4. Run only the next cell. It calls `gemdb.commit()` and then `gemdb.refresh()` to take a new view of the database, and prints the count again. The count now includes the policy you just bought, for example `policies: 902`.

<!-- TODO: GemDB Code's "Refresh Notebook View" toolbar button (GemDB_Code #97, merged 2026-10-05) is not in 1.5.4. Add it here once a release ships it. -->

---

<!--
DRAFT NOTES — remove before publishing

Remaining sections, in Sandeep's order:
  5. MCP

Jupyter section: written 2026-10-06. Verified on the VM: kernel preselected, Run All works (with the
BRAINFREEZE_REPO workaround until Steven's fix). Not yet verified: the four refresh steps (rewritten 2026-10-07 to run single cells, not Run All).

Verified on the VM (GemDB Code 1.5.4, brain-freeze e3b44fc): Before you start, steps 1, 2 (quote,
buy, ID card, claim), and 3 (edits a-e by hand, load, new claim records flavor and toppings).

Test compatibility (Steven's CI reads this README):
- Steven agreed (2026-10-06) to drop the numbered headings; his tests find steps by `## N. `,
  so the tests need updating to match before this merges.
- Commands go in ```sh blocks; the ```console block after one must contain only lines that
  appear in the real output (no "..." lines). Other blocks (python, html) are not checked.
- Steven's tests expect the Jupyter step to contain exactly one python block, `gemdb.refresh()`.
  The draft has none (it uses the notebook's own commit-then-refresh cell, because a bare
  refresh() raises while the session has uncommitted changes). Tests need updating.
- `gemdb web/app.py` is skipped by the tests (long-running), so its console block is not checked.

After the README: edit the intro (first markdown cell) of brain-freeze.ipynb. It is wordy
("no connection string, no driver, no query language and no result set"), internal-facing
(GemStone session, __file__, working directory), says to pick the kernel (VS Code already picks
GemDB (Python in the database)), and has an em dash.

Open decisions:
- Jupyter: consider a note for readers who installed the demo somewhere other than
  ~/GemDB/brain-freeze: set os.environ["BRAINFREEZE_REPO"] = "/home/<your-user>/<path>/brain-freeze"
  in the notebook's first code cell. (Thomas, 2026-10-07; assume the default install needs nothing.)
- Jupyter (verified on the VM, 2026-10-06): the notebook's first code cell cannot find the repo
  after Install Brain Freeze Demo (~/GemDB/brain-freeze). It searches from the database's working
  directory, not the VS Code folder, and every cell that imports brainfreeze then fails. Setting
  os.environ["BRAINFREEZE_REPO"] = "/home/<user>/GemDB/brain-freeze" in that cell fixes it. Steven
  will fix the notebook (2026-10-06), so the README needs no workaround. Retest after his fix.
- Step 2: how to stop and restart the app without Ctrl+C (see the TODO in step 2).
- Spelling: README prose uses American "flavor"; code and on-screen labels keep the app's British
  spelling (`flavour`, "Which flavour?", "Favourite cold treat"). Ask Steven whether to switch the
  app to American spelling ("favourite" is in 15 files, including the data field `favourite_trigger`).
- Step 3: Steven's answer (features/answers/step3.patch) also changes web/wire.py (the JSON API).
  Not needed for the tutorial; confirm with Steven whether step 5's agent needs it.
- Seed output: the console block shows the first and last lines only. Show more as plain text?
- The gemdb -c one-liner is long and quote-heavy. seed.py ends with a friendlier hint
  (book = gemdb.root["brainfreeze"]; book["BF-100539"].total_paid). Keep the one-liner or present it differently?
- Git: the one-click install needs git on the machine. README prerequisite, or should GemDB Code check for it?
- Confirm with James: Sandeep described the install as prompting for a folder; v1.5.4 clones to ~/GemDB/brain-freeze with no prompt.
- Should the README mention the AI agent access (mcp) step, or leave it to the MCP section?
-->
