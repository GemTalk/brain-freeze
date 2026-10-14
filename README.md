# Brain Freeze Insurance

Brain Freeze is a demo app for a fictional insurer that offers friendly coverage for cold-stimulus headaches. It runs on GemDB, which supplies the Python environment and a persistent, object-oriented database. The database stores the data for quotes, policies, and claims, such as each policyholder's age, plan, and premium, and each claim's calculated payment.

The Brain Freeze demo is designed to let you explore some of the basic properties of GemDB databases. But just as important, after you complete the demo, we want you to explore and see how GemDB guarantees ACID (atomic, consistent, isolated, durable) transactions for data that must be correct. After you see how agent-friendly we have made GemDB, reach out to us to learn how to code with GemDB and launch your own application.

Brain Freeze is a demo, not real insurance.

**Note:** Found this repo on GitHub? To run the demo, install [GemDB Code](https://marketplace.visualstudio.com/items?itemName=GemTalkSystems.gemdb) and choose **Install Brain Freeze Demo** from its Getting Started page.

The Brain Freeze demo gives you hands-on experience with GemDB:

- [Load](#load-the-demo-data) sample policies and claims into the database.
- [Launch the web app](#launch-the-web-app), get a quote, buy a policy, and file a claim.
- [Change the schema](#change-the-schema-with-code-not-with-a-table-update) by having an AI agent use Python to add flavors and toppings to claims while the app keeps running.
- [Explore some of the detailed coding in a Jupyter notebook](#explore-the-data-in-a-jupyter-notebook) to learn how GemDB stores this data.
- [Connect an AI agent](#connect-an-ai-agent) to the database using GemDB's provided MCP server, and ask it questions.
- Optionally, [rebrand the website to your needs](#rebrand-the-website-to-your-needs) by having an AI agent do it for you.

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

Brain Freeze has a good problem. A hypothetical study has revealed to GemDB that ice cream fans who can choose their flavors and toppings eat their treats much faster, and faster eating can lead to much more serious cases of brain freeze. To keep up, every claim needs to record the flavor and toppings behind the headache.

In most databases, that means altering a table, migrating the data, and hoping nothing drifts. In GemDB, your code is the schema. You add two fields, `flavour` and `toppings`, to the `Claim` class, and GemDB keeps up atomically and safely. The app keeps running, and the thousands of claims already in the database stay exactly as they are. There is no migration.

First, an AI agent makes the change for you. Then, if you are curious about the details, you can make the primary manual changes yourself.

### Use a Brain Freeze agent to make the change

The repository includes a `schema-evolution` skill for Claude Code, [`.claude/skills/schema-evolution/SKILL.md`](.claude/skills/schema-evolution/SKILL.md). GemDB designed it to change the data schema using Python. The agent adds a field to the classes that GemDB stores and carries the field through the claim form, the claim page, and the JSON API. Finally, the agent loads the changes into the running database and runs the unit tests to ensure the schema changes are live and ready to use. All of this happens without shutting down the Brain Freeze app.

Before you start, ensure you have the **Claude Code for VS Code** extension from Anthropic installed in VS Code. When VS Code prompts you to trust the publisher, choose **Trust Publisher & Install**. Then sign in to Claude Code using your credentials.

1. In the Claude Code sidebar, click **+ New session**.
2. In the chat, enter:

   ```text
   /schema-evolution for the tutorial: add flavors and toppings to claims in my working tree, and ask me which flavors and toppings to offer
   ```

3. Answer the agent's questions. The agent may show a form with a tab for each question, such as **Flavours** and **Toppings**. Click each tab at the top of the form to answer its question. To give your own list, choose **Other**, type the list in the box that appears, and then click **Submit answers**. **Submit answers** stays unavailable until you answer every tab.
4. Wait for the agent to finish, which takes about 90 seconds after you submit your answers. It edits the files, loads the change into the database with `gemdb tools/load.py`, and runs tests to inspect results from the changes. Finally it summarizes what it changed. Depending on your permission mode, Claude Code may prompt you before it edits a file or runs a command. Choose **Yes** to continue.

The agent does not commit the change to Git. Review the results of your changes in a browser. If your browser is still open, reload the page; otherwise, open a new browser window at `http://127.0.0.1:5050/`.

1. Open any policy under **Policies**, and click **File a claim**. The form now asks **Which flavour?** and **Anything on top?**, with the choices you gave the agent.
2. Choose a flavor and one or more toppings, and click **Send the claim**. The claim displays your choices in the summary section, after the claim number.
3. Click **Browse all claims**, and open any previous claim. It loads as before, with no flavor or toppings shown, since it was created before the schema change.

The agent did not migrate any data or restart the app. The running app used the new classes on its next request.

As a thank you for trying the demo so far, click the banner for a real ice cream treat:

[![Schema evolved! Time for ice cream! Now that you've learned about agentic schema evolution, get a free scoop on us! I love ice cream.](images/free-scoop-banner.png)](https://gemdb.com/free-scoop)

### Discard the agent's changes

To try the agent again with different choices, or to make the manual changes in the next section, discard what the agent did. To keep the app running in its existing terminal, open a second terminal in VS Code, and run:

```sh
git restore brainfreeze web
```

```sh
gemdb tools/load.py
```

The first command restores the files the agent changed. The second loads the original classes back into the database. To see the result, reload the claim form. The **Which flavour?** and **Anything on top?** questions are gone now.

The restore reverts the code, but not the data committed in the database. A claim you filed while the change was in place keeps the flavor and toppings data it was saved with. The original `Claim` class does not read them, so the claim page does not show them, since the page no longer renders those values. You can still retrieve the data stored with the claim. If you make the change again, the claim shows them again. In GemDB, objects and the classes that define them are stored separately, so changing a class does not rewrite the objects that were already saved.

### Make the change yourself

The manual steps in the rest of this section make the primary changes the agent completed and tested in about 90 seconds. Follow them if you are curious to see and try those changes yourself.

Before you start the edits, ensure that you reverted the agent's changes, as described in the previous section.

To keep the app running in its existing terminal, open a second terminal in VS Code.

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

Review the results of your changes in a browser:

1. Reload the page. Open any policy under **Policies**, and click **File a claim**. The form now asks **Which flavour?** and **Anything on top?**
2. Choose a flavor and one or more toppings, and click **Send the claim**. The claim now displays details matching your claim choices in the summary section, after the claim number.
3. Click **Browse all claims**, and open any previous claim. It loads as before, with no flavor or toppings shown, since it was created before your database schema changes.

You did not migrate any data, reload the data, or restart the app. `gemdb tools/load.py` loaded your changes into the database, and the running app used them on its next request. The previous claims are still instances of `Claim`, which used the older default values (`None` and `()`), so they show no flavor or toppings.

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

1. Scroll to that section. After **Run All**, the cell that starts `print("policies:"` shows how many policies the notebook sees. Note the number.
2. In your browser, buy another policy: click **Start a quote**, answer the questions, click **See my prices**, and choose a plan.
3. In the notebook, run only the `policies:` cell: click ▷ to the left of the cell, or click in the cell and press **Ctrl+Enter**. Do not click **Run All** or the arrow buttons in the cell's toolbar, because those also run the cells below it. The number has not changed, because the notebook still sees the database as it was.
4. In the notebook toolbar, click **Refresh Notebook View**. A message confirms: "This notebook now sees every commit made so far." If **Refresh Notebook View** shows a `PendingChangesError` that says refresh() would discard uncommitted changes, run the notebook's next code cell instead. It commits your session's changes first, and then takes the new view. Do not use the abort() that the error suggests, because it discards your session's uncommitted work.
5. Run only the `policies:` cell again. The count now includes the policy you just bought.

---

## Connect an AI agent

Claude Code uses the Model Context Protocol (MCP) to work as an AI agent on your behalf with the database. GemDB installations include their own MCP server, which is off until you turn it on.

This step uses Claude Code. Other agents that support MCP can connect to the same server: the client list also offers Claude Desktop and Cursor, or the URL for any other client.

You already installed Claude Code and signed in when you had an agent make the schema change, so you are ready to connect it to GemDB.

1. In the GemDB view, click the **⋯** menu and choose **Connect an AI Agent to GemDB**.
2. A dialog asks **Turn on GemDB's MCP server?** Each connected agent uses one of the limited number of sessions your database allows, which is why the server is off by default. Click **Turn It On**. This dialog appears only while the server is off.
3. Choose **Claude Code**. GemDB connects Claude Code to the `brain-freeze` folder and shows a message that starts "Connected Claude Code to GemDB in brain-freeze."
4. In the Claude Code sidebar, click **+ New session**. If you have a Claude Code session open in a different app, you have to launch a new session to connect with `gemdb`. Use the new session for the rest of this step.
5. To ensure you are connected, enter `/mcp` in the chat. In the Customize area, click **MCP servers**. `gemdb` appears at the top, under **Local**, with the status **Connected**.
6. In the chat, ask Claude Code a question about the policies and claims in the database:

   > Which plan has the highest loss ratio?

Claude Code reads the code in this folder and runs Python against the live database, using the same objects the web app uses.

Depending on your permission mode, Claude Code may prompt you before the agent uses a GemDB tool, for example "Do you want to proceed with `mcp__gemdb__eval_python`?" Click **Details** to read the Python the agent will run. Choose **Yes** to allow it once, or **Yes, allow `mcp__gemdb__eval_python` for this project (just you)** to stop the prompts for that tool. Each GemDB tool has its own prompt.

### Control what the agent can change

Once the MCP server is on, the GemDB view shows an **Agent write access** row. It controls what the agent can do in the GemDB database:

- **can commit** (the default): the agent can read the data, change code, create new data, and save all of its changes to the database.
- **cannot commit**: the agent can read the data and change code, but it cannot save anything to the database.

To switch, click the **Agent write access** row once. GemDB restarts the MCP server, which disconnects any agent that is connected, so start a new Claude Code session afterward. An agent that disconnects badly keeps its database session for up to 30 minutes, so avoid switching the setting repeatedly.

---

## Rebrand the website to your needs

Brain Freeze's look lives in three template files, so an AI agent can give the app a new brand by changing those files. The repository includes a `rebrand` skill for Claude Code, [`.claude/skills/rebrand/SKILL.md`](.claude/skills/rebrand/SKILL.md), and [`BRANDING.md`](BRANDING.md) explains how the look is put together. This step is optional.

1. In the Claude Code sidebar, click **+ New session**.
2. In the chat, enter `/rebrand` followed by a description of your brand, for example its name, main color, fonts, and a logo idea.
3. Wait for the agent to finish. It creates a branch for the brand, changes the brand files, checks the colors for contrast, and summarizes what it changed.
4. Reload the app in your browser. The pages show your brand, with no restart.

To go back to the original look, run:

```sh
git restore web features
```

```sh
git switch main
```
