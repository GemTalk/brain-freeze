# Brain Freeze Insurance

Brain Freeze is a demo app for a fictional insurer that offers friendly coverage for cold-stimulus headaches. It runs on GemDB, which supplies the Python environment and a persistent, object-oriented database. The database stores the data for quotes, policies, and claims, such as each policyholder's age, plan, and premium, and each claim's calculated payment.

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

The initial start takes about 30 seconds, so leave this terminal running while the startup completes. After these lines appear, open the URL in a web browser on the same computer to see the website that Brain Freeze customers use to get a quote, buy a policy, and file a claim.

Buy a policy:

1. Click **Start a quote**.
2. Answer the five questions, and click **See my prices**.
3. Choose a plan, for example **Choose Sundae**. Brain Freeze shows the new policy's ID card, with its policy number (for example, `BF-100900`).

File a claim against it:

1. On the ID card, click **File a claim**.
2. Answer the questions, and click **Send the claim**. The claim displays your Brain Freeze Insurance payout.

Every policyholder is listed under **Policies**, in policy number order, so your latest policies display on the last page. As a convenient alternative, in the **Go to a policy** search, enter a policy number and click **Find**. Every claim is listed under **Claims**, newest first. As each page loads, the app's terminal lists the request.

The app is built with Flask, a popular Python web framework, and the insurance rules are ordinary Python code. Both run inside the database, next to the data. Each quote, policy, and claim is a Python object, and the app reads and changes those objects directly, without an object-relational mapper (ORM) or SQL queries.

Stop the app, and start it again to see that your data is still there:

1. Click in the terminal that is running the app, and press **Ctrl+C**. The terminal prints `KeyboardInterrupt` and a few lines about logging out of the database session, and then shows the shell prompt.
2. To restart the app, re-enter `gemdb web/app.py`. When you reload the page in your browser, you will see that the policy and the claim you created are still there. This data persists because the app committed each one to the database.

---

## Change the schema with code, not with a table update

To improve the app, make each claim record the flavor of ice cream and the toppings that caused the brain freeze. In this step, you add two fields, `flavour` and `toppings`, to the `Claim` class and two questions to the claim form, while the app keeps running. First, an AI agent makes the change for you. Then, if you want to see how much work the agent did, you make the same change by hand.

### Have an agent make the change

The repository includes a skill for Claude Code, [`.claude/skills/schema-evolution/SKILL.md`](.claude/skills/schema-evolution/SKILL.md). It tells an agent how to add a field to the classes that GemDB stores, carry the field through the claim form, the claim page, and the JSON API, and then load the change into the running database.

Before you start, ensure you have the **Claude Code for VS Code** extension from Anthropic installed in VS Code. When VS Code prompts you to trust the publisher, choose **Trust Publisher & Install**. Then sign in to Claude Code using your credentials.

1. In the Claude Code sidebar, click **+ New session**.
2. In the chat, enter:

   ```text
   /schema-evolution for the tutorial: add flavors and toppings to claims in my working tree, and ask me which flavors and toppings to offer
   ```

3. Answer the agent's questions. For example, enter the flavors `cherry, vanilla, chocolate marble, cinnamon`, and then the toppings `nuts, marshmallow, sprinkles, banana, whipped cream`. If the agent asks how the change should land, choose **Just run the tutorial step**, which changes only your working tree.
4. Wait for the agent to finish. It edits the files, loads the change into the database with `gemdb tools/load.py`, checks the result, and summarizes what it changed. Depending on your permission mode, Claude Code may prompt you before it edits a file or runs a command. Choose **Yes** to continue.

The agent does not commit the change to Git. Check the result in your browser:

1. Reload the page. Open any policy under **Policies**, and click **File a claim**. The form now asks **Which flavour?** and **Anything on top?**, with the choices you gave the agent.
2. Choose a flavor and one or more toppings, and click **Send the claim**. The claim displays your choices in the summary section, after the claim number, for example `ice cream (Cherry, sprinkles, banana, whipped cream)`.
3. Click **Browse all claims**, and open any previous claim. It loads as before, with no flavor or toppings shown, since it was created before the schema change.

The agent did not migrate any data or restart the app. The running app used the new classes on its next request.

### Discard the agent's changes

To try the agent again with different choices, or to make the same change by hand in the next section, discard what the agent did. In a second terminal, so the app keeps running in the first (click **+** in the Terminal panel, or press **Ctrl+Shift+`**), run:

```sh
git restore brainfreeze web
```

```sh
gemdb tools/load.py
```

The first command restores the six files the agent changed. The second loads the original classes back into the database. Reload the claim form: the **Which flavour?** and **Anything on top?** questions are gone.

### Make the change yourself

To see how much work the agent did for you, make the same change by hand.

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

**b. [`web/forms.py`](web/forms.py)** (one change)

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

**d. [`web/templates/claim_form.html`](web/templates/claim_form.html)** (one change)

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

**e. [`web/templates/decision.html`](web/templates/decision.html)** (one change)

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
Loaded brainfreeze, brainfreeze.model, forms, lookups, pages, routes_api, routes_html, routes_ops, wire. Committed.
Reload the page: the running app serves what you loaded.
```

Check the result in your browser:

1. Reload the page. Open any policy under **Policies**, and click **File a claim**. The form now asks **Which flavour?** and **Anything on top?**
2. Choose a flavor and one or more toppings, and click **Send the claim**. The claim now displays details matching your claim choices in the summary section, after the claim number, for example `ice cream (Mint choc chip, hot fudge, whipped cream)`.
3. Click **Browse all claims**, and open any previous claim. It loads as before, with no flavor or toppings shown, since it was created before your database schema changes.

You did not migrate any data, reload the book, or restart the app. `gemdb tools/load.py` loaded your changes into the database, and the running app used them on its next request. The previous claims are still instances of `Claim`, which used the older default values (`None` and `()`), so they show no flavor or toppings.

If a page shows **Something went wrong. The terminal running this app has the traceback**, look at the app's terminal for the error. Usually a file is not saved or an edit is missing. Fix the file, save it, and run `gemdb tools/load.py` again.

---

## Explore the data in a Jupyter notebook

In this step, you open a Jupyter notebook that works with the same objects as the web app. Leave the app running in its terminal.

1. In the Explorer, open `brain-freeze.ipynb`.
2. Check the kernel at the top right of the notebook. VS Code selects **GemDB (Python in the database)** for you. If VS Code prompts you to choose a kernel, choose that one.
3. Click **Run All**.

The notebook runs inside the database, so the policies and claims you loaded are already there, with no export or connection string. Its cells show a summary of the book, the loss ratio by risk band, what an approved claim pays out, and where the payouts cluster.

### See another session's changes

The notebook and the web app are separate sessions. Each session sees the database as of its last transaction, so an analysis does not change partway through while other sessions commit. The last section of the notebook, **Seeing another session's commit**, shows this:

1. Scroll to that section. After **Run All**, the cell that starts `print("policies:"` shows how many policies the notebook sees, for example `policies: 901`. Note the number.
2. In your browser, buy another policy: click **Start a quote**, answer the questions, click **See my prices**, and choose a plan.
3. In the notebook, run only the `policies:` cell: click ▷ to the left of the cell, or click in the cell and press **Ctrl+Enter**. Do not click **Run All** or the arrow buttons in the cell's toolbar, because those also run the cells below it. The number has not changed, because the notebook still sees the database as it was.
4. In the notebook toolbar, click **Refresh Notebook View**. A message confirms: "This notebook now sees every commit made so far." If **Refresh Notebook View** shows an error about uncommitted changes, run the notebook's next code cell instead. It commits your session's changes first, and then takes the new view.
5. Run only the `policies:` cell again. The count now includes the policy you just bought, for example `policies: 902`.

---

## Connect an AI agent

Claude Code uses the Model Context Protocol (MCP) to work as an AI agent on your behalf with the database. GemDB installations include their own MCP server, which is off until you turn it on.

The **Agent write access** setting in the GemDB view controls what the agent can do in the GemDB database:

- **cannot commit** (the default): the agent can read the data and change code, but it cannot save anything to the database.
- **can commit**: the agent can read data, change code, create new data, and save all of its changes to the database.

Before you start, ensure you have the **Claude Code for VS Code** extension from Anthropic installed in VS Code. When VS Code prompts you to trust the publisher, choose **Trust Publisher & Install**. Then sign in to Claude Code using your credentials.

1. Optional: To let the agent change the database, click the **Agent write access** row once in the GemDB view so it reads **can commit**. GemDB restarts the MCP server, which disconnects any agent that is connected.
2. In the GemDB view, click the **⋯** menu and choose **Connect an AI Agent to GemDB**.
3. Choose **Claude Code**. GemDB connects Claude Code to the `brain-freeze` folder and shows a message that starts "Connected Claude Code to GemDB in brain-freeze."

   > **REVIEWER QUESTION:** The original README had **Turn It On** before **Claude Code**. On the test VM the MCP server was already on, so **Turn It On** did not appear. Confirm the first-time flow on a clean VM.

4. In the Claude Code sidebar, click **+ New session**. If you have a Claude Code session open in a different app, you have to launch a new session to connect with `gemdb`. Use the new session for the rest of this step.
5. To ensure you are connected, enter `/mcp` in the chat. In the Customize area, click **MCP servers**. `gemdb` appears under **Local**, with the status **Connected**.
6. In the chat, ask Claude Code a question about the policies and claims in the database:

   > Which plan has the highest loss ratio?

Claude Code reads the code in this folder and runs Python against the live database, using the same objects the web app uses.

Claude Code prompts you before the agent uses a GemDB tool, for example "Do you want to proceed with `mcp__gemdb__eval_python`?" Click **Details** to read the Python the agent will run. Choose **Yes** to allow it once, or **Yes, allow `mcp__gemdb__eval_python` for this project (just you)** to stop the prompts for that tool. Each GemDB tool has its own prompt, so expect several during one question.

> **REVIEWER QUESTION:** The schema change by the agent is not written yet. The agent applies Steven's answer patch (`features/answers/step3.patch`) instead of writing the change itself, and a reader who did the schema step by hand already has the change. Options: (A) the reader runs `git restore brainfreeze web` and `gemdb tools/load.py`, then asks; (B) ask for a different change; (C) leave it out until Steven decides. See the DRAFT NOTES.

---

<!--
DRAFT NOTES — remove before publishing

Remaining sections: none. The MCP section ("Connect an AI agent") is drafted; its menu path, the default state of
Agent write access, and the numbers still need a clean first-time pass (see MCP findings below).

Verified on a clean VM pass, 2026-10-12 (ubuntu-demo restored to vscode-deb-base; GemDB Code 1.6.0 from the
Marketplace; Install Brain Freeze Demo cloned brain-freeze 9dba1d0, which is current main, with no prompt;
git was already installed):
- Before you start: the extension starts setup by itself on install; the GemDB view shows Running, Database
  ready, and AI agent access off; Restricted Mode banner, Manage, Trust, and the Workspace Trust tab; gemdb is
  on the PATH of VS Code terminals; Ctrl+` and Ctrl+Shift+` open a terminal (also over Remote Desktop).
- Load the demo data: seed output (900, 4993, 2172 claims, Sundae 179.97); Persisted Objects shows greeting,
  brainfreeze, and brainfreeze_repo after refresh.
- Launch the web app: banner, first start about 30 seconds, quote, plans, ID card BF-100900, claim, Policies
  (policy number order, 50 a page), Claims (newest first), Ctrl+C stop and restart keep the data.
- Change the schema: edits a-e by hand, gemdb tools/load.py output (two lines), new form questions, new claim
  shows flavour and toppings, old claim shows none.
- Jupyter: kernel preselected; Run All runs without errors in about 15 seconds and cell 1 needs no
  BRAINFREEZE_REPO (Steven's fix works); the Refresh Notebook View toolbar button works and shows "This notebook
  now sees every commit made so far."; running a cell with the left play button or Ctrl+Enter keeps the old
  count until the refresh; the toolbar arrow "Execute Cell and Below" also runs the refresh cell below it.
Not yet verified: the "Go to a policy" Find box; the exact text of the Refresh Notebook View error (when the
notebook session has uncommitted changes).

Step 3 restructured 2026-10-13 after Thomas met Sandeep: "Have an agent make the change" (3a), "Discard the agent's changes",
then "Make the change yourself" (the manual edits a-e, now optional, to see how much work the agent did). Verified on a clean
VM (vscode-deb-claude + GemDB Code + Install Brain Freeze Demo + seed; MCP off; default Auto mode; Claude Code 2.1.296):
- The skill ran from a slash command at the start of the message; the agent asked for flavors and toppings (a form with
  tabs, then chat questions), edited six files (model.py, forms.py, routes_html.py, claim_form.html, decision.html, wire.py),
  ran gemdb tools/load.py from its own shell, and left the change in the working tree (git status: six files modified, git
  log unchanged at 9dba1d0, empty stash list). No permission prompts in Auto mode for edits, greps, or git status. The form
  showed the lists; a new claim read "ice cream (Cherry, sprinkles, banana, whipped cream)"; CLM-001285 showed no flavour.
- NOT yet verified: (1) the prompt wording in the draft ("for the tutorial: ... in my working tree, and ask me which ...")
  was written after the tested run, which used "add flavors and toppings to claims, but first ask me which flavors and
  toppings I want to offer" and drew a Scope question ("How should this land, given it collides with README step 3's
  tutorial?", options: Lasting change and rewrite step 3 (Recommended); Lasting change, leave the tutorial broken; Just run the
  tutorial step). Retest with the draft wording; the draft keeps the Scope answer in prose in case it still appears.
  (2) The discard is VERIFIED (2026-10-13, app running, no restart): git restore brainfreeze web, then gemdb tools/load.py
  (prints the usual "Loaded ... Committed." line); the claim form reverted to the original; CLM-002173, filed with a flavor
  under the agent's change, then shows no flavor and no error. The flavor is still stored on that claim (verified with
  gemdb -c: vars(claim) shows 'flavour': 'Cherry' and 'toppings': ('Sprinkles', 'Banana', 'Whipped cream')) and would show
  again if the change is reapplied. The README does not say this; consider one sentence in the discard section: the discard
  reverts the code, not data already saved with it.
  (3) The agent's answers to its questions vary: first a form (choose an option, then Submit answers), then chat.
- Prerequisite paragraph (Claude Code extension, trust publisher, sign in) now appears in 3a and again in "Connect an AI
  agent". Decide whether to keep one.
- CI: Steven's tests read this README's sh blocks. The new `git restore` and `gemdb tools/load.py` blocks have no console block
  on purpose (on a clean tree load.py prints "Nothing had changed", not the Loaded line). The agent steps cannot run in CI.
  Tests need updating, as noted above for the numbered headings.
- Test failures found when the agent ran the unit tests (for Steven): test_tutorial_answer fails once the change is applied
  (expected); three tests.test_notebook failures (TheFirstCellFindsACheckoutBelowWhereTheKernelStarted) and test_ctrl_c
  (AssertionError: 0 == 0 at assertNotEqual(done.returncode, 0); probably expects the pre-1.6.0 Ctrl+C failure).
- The agent ran `git stash && unittest; git stash pop` without prompting in Auto mode. The stash list was empty afterward.
- The VS Code toast "Do you want to install the recommended 'Python' extension from Microsoft?" appears repeatedly during
  agent work. Ask James what a reader should do. The agent's form note ("These two questions went in after 900 policies and
  4,993 episodes were already committed") is copied from the answer patch. It matches a freshly seeded book (900 policies, 4,993 episodes) but is hardcoded, so
  it is stale once a reader adds policies.

MCP findings, 2026-10-13 (VM with MCP already on and Claude Code signed in; Claude Code extension 2.1.296, Sonnet 5, Manual
mode). Verified:
- `/mcp` > MCP servers shows `gemdb` under Local (1), Connected. `schema-evolution` and `rebrand` appear in the slash menu
  among many built-in commands. The agent used the `schema-evolution` skill on its own (shown as a Skill call).
- Prompt wording: "Do you want to proceed with mcp__gemdb__eval_python?" with 1 Yes, 2 Yes, allow
  mcp__gemdb__eval_python for this project (just you), 3 No, and "Tell Claude what to do instead". Details shows the call as
  JSON with the Python in one "code" string. Each GemDB tool prompts separately (eval_python, python_module_state, status,
  abort). Bash find and grep and file reads did not prompt in Manual mode; git apply and gemdb prompted.
- "Which plan has the highest loss ratio?" answered Sundae 0.479, Parfait 0.35, Sprinkle 0.263, 906 policies (900 seeded plus
  6 test policies); numbers on a clean 900-policy book not yet checked. No plan is above 1.0.
- Connect dialogs: with an existing entry, GemDB asks "Claude Code already has a server named "gemdb" for brain-freeze.
  Replace it?" (Cancel / Replace It), then shows "Updated Claude Code to GemDB in brain-freeze. Start a new Claude Code
  session to use it: a session that is already running loaded its MCP servers when it started." plus the command it ran
  (claude mcp add --transport http --scope local gemdb http://127.0.0.1:50390/mcp), "It applies to this folder only.", and
  an undo command (claude mcp remove gemdb --scope local). The first-time message presumably says "Connected" (from
  2026-10-12). `claude` is not on the terminal PATH (GemDB uses the extension's bundled binary under
  ~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude), so the undo command in that dialog does not
  run in a VS Code terminal. Ask James whether the dialog should say how to run it.
- The GemDB view's ⋯ menu: Connect an AI Agent to GemDB, Show Log, Reinstall the Python Execution Engine, Restart the MCP
  Server, Collect Garbage Now, Stop a Database Session..., Install Brain Freeze Demo, Uninstall GemDB.
- Agent write access is a toggle (click the row). Tooltip with can commit: "Agent sessions can change your database and commit.
  Click to make them read-only: their worker gems log in as a database user that cannot commit. The first time, GemDB creates
  that user. Either way the MCP server restarts, which disconnects any agent currently connected." With cannot commit
  (McpReadOnly user) the AI agent access row reads "listening, read-only". Default on a fresh install not yet seen.
- The extension is "Claude Code for VS Code" by Anthropic; installing prompts "Do you trust the publisher "Anthropic"?"
  (Learn More / Cancel / Trust Publisher & Install).
Problems found, for Steven, James, or Sandeep (not for the README):
- The first eval_python call failed with ModuleNotFoundError: No module named 'brainfreeze' (the MCP session did not have the
  checkout on sys.path). The agent recovered after several calls by reading web/app.py (REPO, sys.path.insert) and inserting
  the path itself, plus a wasted python_module_state call (Missing required argument(s): name). It did not recur later,
  probably because the path insert persists in the database session. Retest as the first action on a fresh GemDB start.
- The agent read model.py and analysis.py (and found analysis.least_profitable_plan) before querying, so "needs no
  description of your schema" in the original step 5 is not strictly true.
- Asked to add flavour and toppings, the agent invoked schema-evolution, found features/answers/step3.patch, and applied it
  with git apply (six files: model.py, forms.py, routes_html.py, claim_form.html, decision.html, wire.py) instead of writing
  the change. Steven's call whether the answer patch should stay in the repo.
- `gemdb tools/load.py` failed in the agent's Bash tool (`gemdb: command not found`); the agent did the equivalent import and
  commit through eval_python. gemdb is on the PATH of VS Code terminals only. Question for James.
- A verification read left the session in a transaction. mcp__gemdb__status reported uncommittedChanges=true ("No tool
  commits for you: call commit to persist them or abort to discard them. They are lost when this session ends: 30 minutes of
  inactivity."); the agent called mcp__gemdb__abort ("Transaction aborted; uncommitted changes discarded and the view
  refreshed.").
- The agent ran unittest unasked. Three tests in tests.test_notebook (TheFirstCellFindsACheckoutBelowWhereTheKernelStarted)
  failed under the system python3; the agent says they are unrelated, not verified. test_tutorial_answer failed because the
  answer patch was applied.
- At least 11 permission prompts for one schema change in Manual mode. The README should say prompts are normal.
- The permission-prompt paragraph in the README was written from Manual mode, which Thomas switched to for testing. A
  freshly signed-in Claude Code (extension 2.1.296) starts in Auto mode ("Auto mode is now Claude Code's default
  permission mode ... runs the ones it assesses as lower-risk, and blocks the rest"), so readers may see fewer prompts, or
  different ones. Retest the loss-ratio question in the default mode on the clean pass before keeping that paragraph.
- VS Code showed "Do you want to install the recommended 'Python' extension from Microsoft?" during the session. Ask James
  what a reader should do.
- The new claim form note says "after 900 policies and 4,993 episodes" and the UI spells flavour with a "u".

Test compatibility (Steven's CI reads this README):
- Steven agreed (2026-10-06) to drop the numbered headings; his tests find steps by `## N. `,
  so the tests need updating to match before this merges.
- Commands go in ```sh blocks; the ```console block after one must contain only lines that
  appear in the real output (no "..." lines). Other blocks (python, html) are not checked.
- Steven's tests expect the Jupyter step to contain exactly one python block, `gemdb.refresh()`.
  The draft has none: it uses the Refresh Notebook View toolbar button, with the notebook's own
  commit-then-refresh cell as a fallback in prose (the button refuses, like gemdb.refresh(), while the
  session has uncommitted changes; needs_commit() was False after Run All on the VM). Tests need updating.
- `gemdb web/app.py` is skipped by the tests (long-running), so its console block is not checked.

After the README: edit the intro (first markdown cell) of brain-freeze.ipynb. It is wordy
("no connection string, no driver, no query language and no result set"), internal-facing
(GemStone session, __file__, working directory), says to pick the kernel (VS Code already picks
GemDB (Python in the database)), and has an em dash.

Open decisions:
- Jupyter, non-default install location: the default install needs nothing (verified 2026-10-12). Steven's
  fix (e4167ce) finds the checkout from BRAINFREEZE_REPO, then from where gemdb tools/seed.py ran (recorded in
  the database as gemdb.root["brainfreeze_repo"]), then from ~/GemDB/brain-freeze. Untested for a copy
  cloned elsewhere; a note is probably not needed if the reader ran seed.py from that copy.
- Notebook intro (queued): its first markdown cell still says "Pick the GemDB kernel", still describes the
  checkout path as something "said out loud", and uses em dashes. Cleaning up the notebook's wording is a
  separate job after the README.
- Step 2: stop and restart is now written (Ctrl+C verified on the VM, 2026-10-12, GemDB Code 1.6.0). The terminal
  still prints topaz-style lines ("[Sending soft break]", "Near line 155 of file .../gemdb-run.tpz",
  "ERROR 3004 , a ExitClientError occurred (error 3004)", "Logging out session 1."). Ask James whether
  the ERROR 3004 line can be hidden; until then the step says "a few lines about logging out".
- Future enhancement, after the README is done (Thomas, 2026-10-12): ask Steven and Sandeep whether to run the
  notebook before and after step 3 so a reader can compare. Idea: Run All before step 3 as a baseline; after
  `gemdb tools/load.py`, run the notebook's commit-then-refresh cell and compare, with a scratch cell that prints
  the stored attributes of an old claim and a new one (no existing cell shows claim fields). Not part of the
  README now.
- Step 2: "Go to a policy" + Find is written from the screenshot only. Not yet tested: enter BF-100900, click Find.
- Spelling: README prose uses American "flavor"; code and on-screen labels keep the app's British
  spelling (`flavour`, "Which flavour?", "Favourite cold treat"). Ask Steven whether to switch the
  app to American spelling ("favourite" is in 15 files, including the data field `favourite_trigger`).
- Step 3: Steven's answer (features/answers/step3.patch) also changes web/wire.py (the JSON API).
  Not needed for the tutorial; confirm with Steven whether step 5's agent needs it.
- Seed output: the console block shows the first and last lines only. Show more as plain text?
- The gemdb -c one-liner is long and quote-heavy. seed.py ends with a friendlier hint
  (book = gemdb.root["brainfreeze"]; book["BF-100539"].total_paid). Keep the one-liner or present it differently?
- Git: the one-click install needs git on the machine. README prerequisite, or should GemDB Code check for it?
- Install Brain Freeze Demo: answered. It clones to ~/GemDB/brain-freeze with no prompt (GemDB Code
  CHANGELOG, no folder prompt since 1.5.2; verified on 1.6.0). It clones the current main, so the README
  must stay in step with main. The command does not check for git (src/demo.ts).
- Should the README mention the AI agent access (mcp) step, or leave it to the MCP section?
- Requirements statement (Thomas, 2026-10-13): add one near "Before you start": GemDB Code on a supported platform, a
  Claude account that can sign in to Claude Code, and a window large enough for the chat and the app. Write it after the
  clean pass; do not say anything about permission modes or effort levels (readers' settings vary).
- MCP section, still to settle on a clean first-time pass (restore 1.6.0-before-mcp): the first-time menu path and whether
  **Turn It On** exists; the default state of Agent write access (the draft says cannot commit is the default, from
  Thomas; confirm) and whether the loss-ratio question works with cannot commit (untested; the test ran with can commit); whether the first question hits
  ModuleNotFoundError; the numbers on a clean 900-policy book; the schema change by the agent (options A, B, C above).
-->
