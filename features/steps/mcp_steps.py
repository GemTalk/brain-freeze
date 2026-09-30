"""Step 5 of the tutorial: an agent working on the live book over MCP.

No language model is involved, on purpose. What the tutorial promises is that
an agent CAN answer from the live objects -- that the server is there, offers
`eval_python`, and runs Python against the same book everything else sees. A
model's phrasing is not something a suite can pin; the protocol is.

The server is set up the way GemDB Code sets it up when you turn it on: its
own bundled payload, filed in with `install.sh --grail --no-auth`, and a router
forked with the core toolsets plus McpGrailToolset (GemDB_Code src/mcp.ts,
`startRouter`). It serves on its own port, so it cannot collide with a router
someone has connected Claude Code to.
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

from behave import then, when

from environment import REPO, gemdb_env, keep

sys.path.insert(0, os.path.join(REPO, "tools"))
from mcp_questions import Client, preamble     # noqa: E402

PORT = 50391
GRAIL_TOOLSET = "McpGrailToolset"


def database():
    """What topaz needs to reach the database this run's `gemdb` uses."""
    wrapper = shutil.which("gemdb", path=gemdb_env()["PATH"])
    with open(wrapper) as handle:
        text = handle.read()
    value = {k: re.search(r'^%s="(.*)"$' % k, text, re.M).group(1)
             for k in ("ROOT", "GEMSTONE", "GRAIL_DIR", "STONE")}
    root, stone = value["ROOT"], value["STONE"]
    env = dict(os.environ)
    env.update({
        "GEMSTONE": value["GEMSTONE"],
        "GEMSTONE_GLOBAL_DIR": root,
        "GEMSTONE_SYS_CONF": os.path.join(root, "db", "conf"),
        "GEMSTONE_EXE_CONF": os.path.join(root, "db", "conf"),
        # The router forks its workers through a NetLDI; without this it looks
        # for gs64ldi. GemDB's is `<stone>ldi`, and so is the fresh one's.
        "GEMSTONE_NRS_ALL": "#netldi:%sldi#dir:%s" % (stone, root),
        "GRAIL_DIR": value["GRAIL_DIR"],
        "PATH": os.path.join(value["GEMSTONE"], "bin") + os.pathsep + os.environ["PATH"],
        "GS_STONE": stone, "GS_USER": "DataCurator", "GS_PASS": "swordfish",
        "MCP_PORT": str(PORT),
    })
    return env, value


def payload():
    """GemDB Code's MCP payload: GEMDB_EXTENSION's, if set, as for
    tools/fresh_database.sh; otherwise the newest installed in an editor."""
    if os.environ.get("GEMDB_EXTENSION"):
        return os.path.join(os.environ["GEMDB_EXTENSION"], "mcp")
    found = sorted(glob.glob(os.path.expanduser(
        "~/.vscode*/extensions/gemtalksystems.gemdb-*/mcp")))
    assert found, "GemDB Code's MCP payload is not installed"
    return found[-1]


def topaz(env, script):
    return subprocess.run(["topaz", "-l", "-q"], input=script, env=env,
                          capture_output=True, text=True, timeout=300)


@when("GemDB's MCP server is turned on")
def turn_on_mcp(context):
    env, value = database()
    work = tempfile.mkdtemp(prefix="bf-mcp-")
    shutil.copytree(payload(), os.path.join(work, "mcp"))
    installed = subprocess.run(["bash", "install.sh", "--grail", "--no-auth"],
                               cwd=os.path.join(work, "mcp"), env=env,
                               capture_output=True, text=True, timeout=600)
    assert installed.returncode == 0, (
        "the MCP server did not install:\n%s%s"
        % (installed.stdout[-2000:], installed.stderr[-2000:]))

    started = topaz(env, "\n".join([
        "set user DataCurator pass swordfish",
        "set gemstone %s" % value["STONE"],
        "login",
        "run",
        "| r |",
        "r := McpRouter new.",
        "r toolsetNames: (McpServer defaultToolsetNames copyWith: '%s')." % GRAIL_TOOLSET,
        "r toolsetOptions: (Dictionary new",
        "  at: '%s' put: (Dictionary new" % GRAIL_TOOLSET,
        "    at: 'grailDirectory' put: '%s'; yourself);" % value["GRAIL_DIR"],
        "  yourself).",
        "r serverTitle: 'brain-freeze acceptance'.",
        "r forkOnPort: %d" % PORT,
        "%",
        "logout",
        "exit",
    ]) + "\n")
    session = re.search(r"gem session (\d+)", started.stdout)
    assert session, "the MCP router did not start:\n%s%s" % (
        started.stdout[-2000:], started.stderr[-2000:])
    context.mcp = {"env": env, "work": work, "session": session.group(1)}
    context.add_cleanup(stop_mcp, context)

    context.agent = Client(port=PORT)
    context.agent.url = "http://127.0.0.1:%d/mcp" % PORT
    for attempt in range(30):
        try:
            context.agent_server = context.agent.open()
            break
        except Exception:
            import time
            time.sleep(1)
    else:
        raise AssertionError("nothing answered MCP on port %d" % PORT)
    context.add_cleanup(context.agent.close)


def stop_mcp(context):
    env, value = database()
    topaz(env, "\n".join([
        "set user DataCurator pass swordfish",
        "set gemstone %s" % value["STONE"],
        "login",
        "run",
        "System stopSession: %s" % context.mcp["session"],
        "%",
        "logout",
        "exit",
    ]) + "\n")
    shutil.rmtree(context.mcp["work"], ignore_errors=True)


@then("the agent is offered a way to run Python")
def offered_python(context):
    tools = context.agent.rpc("tools/list")["result"]["tools"]
    names = sorted(t["name"] for t in tools)
    context.agent_tools = names
    assert "eval_python" in names, "no eval_python among %s" % names


#: What the agent is asked, after the preamble docs/mcp-questions.md tells an
#: agent to run. The same code is then run directly in a session of its own,
#: so the agent's answer is checked against the live book rather than against
#: figures pinned before steps 2 and 4 bought policies.
QUESTION = (
    "print(analysis.least_profitable_plan(book))\n"
    "print(len(book))\n")


@when("the agent asks which plan is losing money")
def agent_asks(context):
    context.agent.python(preamble())
    context.agent_answer = context.agent.python(QUESTION)


@then("it answers from the live book, as a session of its own would")
def answers_from_the_live_book(context):
    direct = subprocess.run(["gemdb", "-c", preamble() + QUESTION], cwd=REPO,
                            env=gemdb_env(), capture_output=True, text=True)
    assert direct.returncode == 0, direct.stdout[-1500:] + direct.stderr[-1500:]
    expected = [line for line in direct.stdout.strip().splitlines() if line.strip()][-2:]
    keep(context, "what the agent was asked and answered",
         "server: %s\ntools: %s\n\nasked:\n%s\nanswered:\n%s\n\nasked directly:\n%s\n"
         % (context.agent_server, ", ".join(context.agent_tools), QUESTION,
            context.agent_answer, "\n".join(expected)),
         extension="txt")
    for line in expected:
        assert line.strip() in context.agent_answer, (
            "a session of its own answers %r, and the agent answered:\n%s"
            % (line, context.agent_answer))
