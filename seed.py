"""Load the Brain Freeze Insurance dataset into GemDB as objects.

    gemdb seed.py                 # load, commit, report
    gemdb seed.py --dry-run       # build the objects, report, commit nothing
    python3 seed.py --dry-run     # same, under CPython, for checking the parse

There is no import tool here and no schema to declare. This reads two CSVs,
makes ordinary Python objects, puts one of them in `gemdb.root`, and commits.
That is the whole of what the PRD called a separate workstream.

WHAT ENDS UP IN THE DATABASE

    gemdb.root["brainfreeze"]           a Book
        .policies["BF-100539"]          a Policyholder
            .events                     every cold treat, oldest first
                [0].claim               a Claim, or None

Re-running REPLACES `gemdb.root["brainfreeze"]` wholesale. The old graph is
left unreferenced and the garbage collector deals with it; nothing is merged,
appended or deduplicated, so a second run is a clean reset rather than a
double load. That is deliberate -- resetting the demo is "run it again".

ONE THING TO VERIFY BEFORE RELYING ON THIS

Grail compiles a Python class into a real GemStone class, and these classes
are defined by importing `brainfreeze.model`. Whether a later session's import
binds to the same class as the committed instances, or compiles a fresh one
and orphans them, is the question this script is built on and cannot answer by
itself. Check it the short way: run this, quit, start a new session, and see
whether `gemdb.root["brainfreeze"]["BF-100539"].total_paid` still answers. If
it does not, the fix is to define these classes once inside the database
rather than on every import -- a change to how the package is loaded, not to
the model.
"""

import csv
import os
import sys
from datetime import date

from brainfreeze.model import Book, Claim, Event, Policyholder

#: `data/` beside this file, not beside the working directory. `gemdb seed.py`
#: and the tests both need to find these whatever directory they start from.
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
POLICYHOLDERS_CSV = os.path.join(_DATA, "policyholders.csv")
CLAIMS_CSV = os.path.join(_DATA, "claims.csv")
ROOT_KEY = "brainfreeze"


# -- reading the CSVs -------------------------------------------------------
# pandas writes an empty field for a missing value and the words True/False
# for a boolean, so both need turning back into Python by hand.

def _bool(text):
    return text == "True"


def _float(text):
    return float(text) if text else None


def _int(text):
    return int(text) if text else None


def _text(value):
    return value if value else None


def _date(text):
    year, month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)


def read_policyholders(path=POLICYHOLDERS_CSV):
    """Build a Book of policyholders, with no events attached yet."""
    book = Book()
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            book.add(Policyholder(
                policy_id=row["policy_id"],
                age=int(row["age"]),
                sex=row["sex"],
                migraine_history=_bool(row["migraine_history"]),
                tension_type_headache_history=_bool(row["tension_type_headache_history"]),
                typical_consumption_speed=row["typical_consumption_speed"],
                favourite_trigger=row["favorite_trigger"],
                underwriting_base=float(row["underwriting_base"]),
                plan_name=row["coverage_plan"],
                annual_premium=float(row["annual_premium_usd"]),
                policy_start_date=_date(row["policy_start_date"]),
                policy_term_months=int(row["policy_term_months"]),
                policy_status=row["policy_status"],
                policy_lapse_date=_date(row["policy_lapse_date"]) if row["policy_lapse_date"] else None,
            ))
    return book


def attach_events(book, path=CLAIMS_CSV):
    """Hang every cold treat off its policyholder, claim and all.

    The CSV is one row per EVENT, not per claim -- most rows never became a
    claim, and those are the ones that make frequency computable. A row with a
    claim_id gets a Claim; the rest get None.
    """
    missing = set()
    attached = 0
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            policy_id = row["policy_id"]
            policyholder = book.policies.get(policy_id)
            if policyholder is None:
                missing.add(policy_id)
                continue

            claim = None
            if row["claim_id"]:
                claim = Claim(
                    claim_id=row["claim_id"],
                    requested=float(row["claim_amount_requested_usd"]),
                    approved=float(row["claim_amount_approved_usd"]),
                    status=row["claim_status"],
                    reason=_text(row["denial_reason"]),
                )

            policyholder.add_event(Event(
                event_id=row["event_id"],
                event_date=_date(row["event_date"]),
                trigger=row["trigger_type"],
                temperature_c=float(row["item_temperature_c"]),
                portion_ml=_float(row["portion_size_ml"]),
                consumption_speed=row["consumption_speed"],
                brain_freeze=_bool(row["brain_freeze_occurred"]),
                onset_sec=_float(row["onset_time_sec"]),
                duration_sec=_float(row["duration_sec"]),
                pain_intensity=_float(row["pain_intensity_nrs"]),
                pain_location=_text(row["pain_location"]),
                pain_quality=_text(row["pain_quality"]),
                claim=claim,
            ))
            attached += 1

    if missing:
        raise SystemExit(
            "%d event rows name a policy that is not in %s, e.g. %s. The two "
            "files are out of step -- regenerate both." % (
                len(missing), POLICYHOLDERS_CSV, sorted(missing)[0]))
    return attached


def load(policyholders_csv=POLICYHOLDERS_CSV, claims_csv=CLAIMS_CSV):
    """Read both files and return the finished object graph."""
    book = read_policyholders(policyholders_csv)
    attach_events(book, claims_csv)
    return book


# -- the smoke test, so a load reports rather than just finishing -----------

def report(book):
    """Print enough to see at a glance that the load worked."""
    events = book.events
    claims = book.claims
    approved = [c for c in claims if c.is_approved]
    froze = [e for e in events if e.brain_freeze]

    print("Loaded %d policyholders and %d cold-treat events." % (len(book), len(events)))
    print()
    print("  brain freeze in            %d of %d events (%.1f%%)" % (
        len(froze), len(events), 100.0 * len(froze) / len(events)))
    print("  claims filed               %d" % len(claims))
    print("  approved                   %d" % len(approved))
    print("  refused                    %d" % (len(claims) - len(approved)))
    print("  premium collected          $%.2f" % book.total_premium)
    print("  paid out                   $%.2f" % book.total_paid)
    print("  loss ratio                 %.2f" % book.loss_ratio)
    print()

    tiers = {}
    for policyholder in book:
        tiers.setdefault(policyholder.risk_tier, []).append(policyholder)
    print("  by tier:")
    for tier in ("Low", "Medium", "High"):
        group = tiers.get(tier, [])
        if not group:
            continue
        premium = sum(p.annual_premium for p in group)
        paid = sum(p.total_paid for p in group)
        print("    %-7s %3d policies   premium $%9.2f   paid $%9.2f   loss ratio %.2f" % (
            tier, len(group), premium, paid, (paid / premium) if premium else 0.0))
    print()

    sample = book.policies.get("BF-100539")
    if sample is not None:
        print("  %s: %d events, %d claims, %d approved, $%.2f paid, cap %d of %d used" % (
            sample.policy_id, len(sample.events), len(sample.claims),
            len(sample.approved_claims), sample.total_paid,
            len(sample.approved_claims), len(sample.approved_claims) + sample.claims_remaining_this_year))


def seed_database(argv):
    dry_run = "--dry-run" in argv
    book = load()

    if dry_run:
        report(book)
        print("Dry run: nothing was committed.")
        return 0

    import gemdb

    replacing = ROOT_KEY in gemdb.root
    gemdb.root[ROOT_KEY] = book
    gemdb.commit()

    report(book)
    print('%s gemdb.root["%s"]. Committed.' % (
        "Replaced" if replacing else "Wrote", ROOT_KEY))
    print()
    print("From here:")
    print('    book = gemdb.root["%s"]' % ROOT_KEY)
    print('    book["BF-100539"].total_paid')
    return 0


if __name__ == "__main__":
    sys.exit(seed_database(sys.argv[1:]))
