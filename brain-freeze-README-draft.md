# Brain Freeze Insurance

Brain Freeze is a demo app for a fictional insurer that offers friendly coverage for cold-stimulus headaches. It runs on GemDB, which supplies the Python environment and persistent database behind every quote, policy, and claim. Brain Freeze is a demo, not real insurance.

<!-- TODO: short "what's in this repo" paragraph (per Sandeep): dataset generator/loader, the brainfreeze data model, and the web app. Write once those pieces have been walked through. -->

**Note:** Found this repo on GitHub? To run the demo, install [GemDB Code](https://marketplace.visualstudio.com/items?itemName=GemTalkSystems.gemdb) and choose **Install Brain Freeze Demo** from its Getting Started page.

---

## Before you start

1. In VS Code, install **GemDB Code** and follow its Getting Started steps. Wait until the GemDB panel shows **Database: ready**.
2. From the same Getting Started page, choose **Install Brain Freeze Demo**. GemDB Code clones this repo into `~/GemDB/brain-freeze` and opens it in VS Code.
3. VS Code opens the folder in **Restricted Mode**. Click **Manage** in the banner, click **Trust**, and then close the **Workspace Trust** tab.
4. Open a terminal: **Terminal → New Terminal**, or press **Ctrl+`**. (On a narrow window, the Terminal menu is under **…**.)

Every command below runs in a VS Code terminal, from the `brain-freeze` folder. `gemdb` is a command-line tool: it runs a Python script inside the database.

---

## 1. Load data

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

```console
Sundae 179.97
```

There is no schema file and no save method. `gemdb.root` is a dictionary that persists, and `gemdb.commit()` is the only call that writes.

---

## 2. Launch the web app

```sh
gemdb web/app.py
```

```console
Brain Freeze Insurance is running.

  Open:  http://127.0.0.1:5050/
```

Leave this terminal running: it is the app. Open <http://127.0.0.1:5050/> in a web browser on the same computer.

Buy a policy:

1. Click **Start a quote**.
2. Answer the five questions, and click **See my prices**.
3. Choose a plan, for example **Choose Sundae**. Brain Freeze shows the new policy's ID card, with its policy number (for example, `BF-100900`).

File a claim against it:

1. On the ID card, click **File a claim**.
2. Answer the questions, and click **Send the claim**. The decision page shows what the claim pays.

Every policyholder is listed under **Policies**, and every claim under **Claims**. As each page loads, the app's terminal lists the request.

The app is plain Flask, and the insurance rules are plain Python. Each quote, policy, and claim is a Python object, and the app reads and writes those objects in the database directly, with no object-relational mapper (ORM) and no SQL in between.

<!-- TODO: the "stop the app and start it again" persistence check. On GemDB Code 1.5.4, Ctrl+C drops to a `topaz 1>` prompt instead of stopping the app (brain-freeze tests/test_ctrl_c.py). Users must not see topaz. Waiting on Steven / GemDB Code for a clean way to stop the app. -->

---

## 3. Change the schema

Claims should record which ice cream caused the brain freeze. In this step, you add two fields to the `Claim` class and two questions to the claim form, while the app keeps running.

Leave the app running in its terminal. Open a second terminal for this step: click **+** in the Terminal panel, or press **Ctrl+Shift+`**.

Make the following edits in VS Code, and save each file (**Ctrl+S**). To find each spot, search the file (**Ctrl+F**) for the line named in each edit.

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
2. Choose a flavour and one or more toppings, and click **Send the claim**. The decision page shows them after the claim number, for example `ice cream (Mint choc chip, hot fudge, whipped cream)`.
3. Click **Browse all claims**, and open a claim dated before today. It loads as before, with no flavour or toppings shown.

You did not migrate any data, reload the book, or restart the app. `gemdb tools/load.py` loaded your changes into the database, and the running app used them on its next request. The 2,172 older claims are still instances of `Claim`, and they read the new fields' default values (`None` and `()`), so they show no flavour or toppings.

If a page shows **Something went wrong. The terminal running this app has the traceback**, look at the app's terminal for the error. Usually a file is not saved or an edit is missing. Fix the file, save it, and run `gemdb tools/load.py` again.

---

<!--
DRAFT NOTES — remove before publishing

Remaining sections, in Sandeep's order:
  4. Jupyter
  5. MCP

Verified on the VM (GemDB Code 1.5.4, brain-freeze e3b44fc): Before you start, steps 1, 2 (quote,
buy, ID card, claim), and 3 (edits a-e by hand, load, new claim records flavour and toppings).

Test compatibility (Steven's CI reads this README):
- Keep the `## N. ` headings.
- Commands go in ```sh blocks; the ```console block after one must contain only lines that
  appear in the real output (no "..." lines). Other blocks (python, html) are not checked.
- Step 4 must contain exactly one python block: `gemdb.refresh()`.
- `gemdb web/app.py` is skipped by the tests (long-running), so its console block is not checked.

Open decisions:
- Step 2: how to stop and restart the app without Ctrl+C (see the TODO in step 2).
- Step 3: the code spells "flavour" (British); American readers may type "flavor". Keep, or ask
  Steven to switch?
- Step 3: Steven's answer (features/answers/step3.patch) also changes web/wire.py (the JSON API).
  Not needed for the tutorial; confirm with Steven whether step 5's agent needs it.
- Seed output: the console block shows the first and last lines only. Show more as plain text?
- The gemdb -c one-liner is long and quote-heavy. seed.py ends with a friendlier hint
  (book = gemdb.root["brainfreeze"]; book["BF-100539"].total_paid). Keep the one-liner or present it differently?
- Git: the one-click install needs git on the machine. README prerequisite, or should GemDB Code check for it?
- Confirm with James: Sandeep described the install as prompting for a folder; v1.5.4 clones to ~/GemDB/brain-freeze with no prompt.
- Should the README mention the AI agent access (mcp) step, or leave it to the MCP section?
-->
