"""Generate docs/mcp-questions.md by running every answer.

    gemdb make_mcp_questions.py

The point of generating it: a document that lists what an agent can ask, with
answers typed in by hand, is a promise nobody checked. This one runs each
snippet inside the database and writes down what actually came back, so the
answers cannot be wrong -- and regenerating it after a data change is how you
find out the demo's promises have drifted.

It re-seeds first, deliberately. The answers have to describe a freshly
seeded database -- CUJ-0's starting state, and the figures `tests/test_seed.py`
pins -- not whatever the last demo or test run left behind. Generating against
a dirty database was the first thing this script got wrong: it reported 901
policies because the app's tests had filed claims.

Each entry is the Python an agent would send through GemDB's `eval_python` or
`execute_code`. There is no tool that knows what a policyholder is; that is
the design, and `brainfreeze.analysis` exists so the agent composes named
questions rather than deriving aggregates and getting a denominator wrong.
"""

import io
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREAMBLE = """import gemdb
from brainfreeze import analysis
book = gemdb.root["brainfreeze"]"""

QUESTIONS = [
    ("How big is this book, and is it making money?",
     "analysis.book_summary(book)",
     "The one-liner an agent should open with. `loss_ratio` under 1.0 means "
     "the book is profitable overall."),

    ("What is the loss ratio by risk tier?",
     "analysis.loss_ratio_by_tier(book)",
     "The demo's punchline. The 1.9x loading on High over-prices the risk, so "
     "the customers the underwriter fears most are the most profitable, and "
     "the middle of the book is where the money leaks."),

    ("Which coverage plan is least profitable?",
     "analysis.least_profitable_plan(book)",
     "Returned as (name, ratio) so the agent can quote both."),

    ("What share of claims get paid, and why are the rest refused?",
     "(analysis.claim_approval_rate(book), analysis.denial_reasons(book))",
     "Refusal reasons come from `brainfreeze.adjudication`, not from the app, "
     "so this answer and the claim screen cannot disagree."),

    ("Why was CLM-001291 refused?",
     "[(e.claim.claim_id, e.claim.reason, e.event_date, "
     "p.policy_lapse_date, p.is_in_force_on(e.event_date))\n"
     " for p in book for e in p.events\n"
     " if e.claim is not None and e.claim.claim_id == 'CLM-001291']",
     "CUJ-2. The refusal is not a stored string an agent has to trust -- the "
     "event date, the lapse date and the in-force test are all there, so the "
     "reason can be checked rather than repeated."),

    ("Why is BF-100539 in the Medium band?",
     "brainfreeze.score_breakdown(\n"
     "    book['BF-100539'].age,\n"
     "    book['BF-100539'].migraine_history,\n"
     "    book['BF-100539'].tension_type_headache_history,\n"
     "    book['BF-100539'].typical_consumption_speed,\n"
     "    book['BF-100539'].favourite_trigger,\n"
     "    base=book['BF-100539'].underwriting_base)",
     "Only answerable because the drawn base is recorded. Before that column "
     "existed the score could not be reproduced from the answers beside it, "
     "and this question had no honest answer."),

    ("Which policies are we underpricing?",
     "[(p.policy_id, p.plan_name, p.risk_tier, ratio)\n"
     " for p, ratio in analysis.top_n_by_loss_ratio(book, 5)]",
     "Above 1.0 the policy has cost more than it brought in."),

    ("How often does a cold treat actually cause brain freeze?",
     "{'events': len(book.events),\n"
     " 'caused a headache': len([e for e in book.events if e.brain_freeze]),\n"
     " 'rate': round(len([e for e in book.events if e.brain_freeze])\n"
     "               / len(book.events), 3)}",
     "Only computable because the events that hurt nobody are stored too. A "
     "model that kept claims alone would have thrown the denominator away and "
     "this question could not be asked at all."),

    ("Which customers claim most often?",
     "[(p.policy_id, rate) for p, rate in "
     "analysis.top_n_by_expected_claims(book, 5)]",
     "Quote the `min_events` floor with the answer: without it the ranking is "
     "a list of the shortest histories in the book, not the likeliest "
     "claimants."),
]


def run(expression, namespace):
    """Evaluate as `eval_python` would, and return the repr of the value."""
    return repr(eval(compile(expression, "<question>", "eval"), namespace))


def wrap(text, width=76, indent=""):
    words, lines, line = text.split(), [], indent
    for word in words:
        if len(line) + len(word) + 1 > width and line.strip():
            lines.append(line.rstrip())
            line = indent + word
        else:
            line = (line + " " + word) if line.strip() else indent + word
    if line.strip():
        lines.append(line.rstrip())
    return "\n".join(lines)


def main():
    import gemdb
    import seed

    # A clean book, so the answers match tests/test_seed.py rather than
    # whatever the last run left behind.
    gemdb.root["brainfreeze"] = seed.load()
    gemdb.commit()

    namespace = {}
    exec(compile(PREAMBLE, "<preamble>", "exec"), namespace)
    import brainfreeze
    namespace["brainfreeze"] = brainfreeze

    out = io.StringIO()
    out.write("# Questions this demo promises to answer\n\n")
    out.write(wrap(
        "GemDB's MCP surface is code-level, not data-level: it offers "
        "`eval_python`, `execute_code`, `commit`/`abort`/`refresh`, browsing "
        "and search. **There is no tool that knows what a policyholder is.** "
        "An agent answers these by writing Python that runs inside the "
        "database.") + "\n\n")
    out.write(wrap(
        "Every answer below was produced by running the snippet beside it, "
        "not typed in, against a **freshly seeded** database -- the state "
        "CUJ-0 starts from and the figures `tests/test_seed.py` pins. "
        "Regenerate with `gemdb make_mcp_questions.py` after any change to "
        "the data or the rules; if an answer moves, either the change was "
        "wrong or this file is the record of what the demo now promises.")
        + "\n\n")
    out.write("Each snippet assumes this preamble:\n\n```python\n"
              + PREAMBLE + "\n```\n\n---\n")

    failures = 0
    for number, (question, code, note) in enumerate(QUESTIONS, 1):
        out.write("\n## %d. %s\n\n" % (number, question))
        out.write(wrap(note) + "\n\n```python\n" + code + "\n```\n\n")
        try:
            answer = run(code, namespace)
        except Exception:
            failures += 1
            answer = "FAILED\n" + traceback.format_exc()
        out.write("```\n" + answer + "\n```\n")
        print("  %d. %s" % (number, "ok" if "FAILED" not in answer else "FAILED"))

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "docs", "mcp-questions.md")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(out.getvalue())

    print("\nWrote docs/mcp-questions.md (%d questions, %d failed)"
          % (len(QUESTIONS), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
