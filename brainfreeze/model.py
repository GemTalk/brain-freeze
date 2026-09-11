"""The objects that live in the database.

A policyholder holds every cold treat they recorded, in order, and each of
those may or may not have a claim attached. That shape is deliberate and it is
the one thing here worth arguing about, so: the obvious model is a
policyholder holding a list of *claims*, and it is wrong. Most of what happens
to a policyholder is a cold treat that hurt nobody, and those rows are the
denominator. Throw them away and "how often does a slushie cause brain
freeze" stops being a question the data can answer -- which is most of what
the notebook and the agent are for.

So: `Policyholder.events` is the list. `claims` is derived from it.

Standard library only, like the rest of the package, because these classes are
instantiated inside the database where numpy and pandas do not exist.
"""

from datetime import timedelta

from .adjudication import (
    ANNUAL_CLAIM_LIMIT,
    REASON_OUTSIDE_TERM,
    REASON_POLICY_LAPSED,
)
from .money import ZERO, format_usd, round_cents, round_half_up, usd
from .underwriting import COVERAGE_PLANS, risk_score, risk_tier


class Claim:
    """A claim filed against one cold-treat event."""

    #: Added in CUJ-4, after the sample data was already committed. They are
    #: class attributes as well as instance ones on purpose: a claim written
    #: before the fields existed has no flavour slot of its own, and without a
    #: default here reading `claim.flavour` on one of those raises
    #: AttributeError. This one line is the whole migration.
    flavour = None
    toppings = ()

    #: Which rule refused this claim, as a stable identifier, alongside
    #: the sentence in `reason`. Same class-attribute default and the same
    #: reason for it -- but note what docs/prd-corrections.md measured: a
    #: default declared *after* records are committed is not visible to those
    #: records, because editing the class compiles a different one. Claims
    #: already in the database therefore raise AttributeError on `.rule`, and
    #: anything reading it across the whole book must go through
    #: `getattr(claim, "rule", None)`. `analysis.denial_rules` does.
    rule = None

    def __init__(self, claim_id, requested, approved, status, reason=None,
                 flavour=None, toppings=None, rule=None):
        self.claim_id = claim_id
        #: Through `usd`, which refuses a float outright. Money enters the
        #: model here and at Policyholder, and nowhere else, so those two
        #: calls are the whole guarantee that none of it is a float.
        self.requested = usd(requested)
        self.approved = usd(approved)
        self.status = status
        self.reason = reason
        if rule is not None:
            self.rule = rule
        if flavour is not None:
            self.flavour = flavour
        if toppings is not None:
            self.toppings = tuple(toppings)

    @property
    def is_approved(self):
        return self.status == "Approved"

    def __repr__(self):
        return "<Claim %s %s %s>" % (self.claim_id, self.status,
                                     format_usd(self.approved))


class Event:
    """One cold treat, whether or not it caused anything."""

    def __init__(self, event_id, event_date, trigger, temperature_c, portion_ml,
                 consumption_speed, brain_freeze, onset_sec=None, duration_sec=None,
                 pain_intensity=None, pain_location=None, pain_quality=None, claim=None):
        self.event_id = event_id
        self.event_date = event_date
        self.trigger = trigger
        self.temperature_c = temperature_c
        self.portion_ml = portion_ml
        self.consumption_speed = consumption_speed
        self.brain_freeze = brain_freeze
        self.onset_sec = onset_sec
        self.duration_sec = duration_sec
        self.pain_intensity = pain_intensity
        self.pain_location = pain_location
        self.pain_quality = pain_quality
        self.claim = claim

    @property
    def claimed(self):
        return self.claim is not None

    def __repr__(self):
        return "<Event %s %s %s%s>" % (
            self.event_id, self.event_date, self.trigger,
            "" if self.brain_freeze else " (no brain freeze)")


def event_order(event):
    """The sort key behind "oldest first" -- date, then event id.

    The date is the promise, and on its own it is not a total order: 37
    policies in the committed data record two cold treats on the same day. A
    date-only sort leaves those pairs wherever they arrived, which is the bug
    again with an extra step -- Python's sort is stable, so ties fall back on
    the row order in the CSV, and that is precisely the thing that must stop
    deciding anything.

    `event_id` breaks them. It is unique across the file, never empty, and
    zero-padded to a fixed width, so comparing the strings compares the
    numbers; `app.py` mints new ones through the same `EVT-%06d` series. That
    makes the loaded order a function of the rows themselves rather than of
    the sequence they were read in: shuffle the file and every policy comes
    back in exactly the order it is in now.
    """
    return (event.event_date, event.event_id)


class Policyholder:
    """One policy, and everything that has happened under it."""

    def __init__(self, policy_id, age, sex, migraine_history,
                 tension_type_headache_history, typical_consumption_speed,
                 favourite_trigger, underwriting_base, plan_name,
                 annual_premium, policy_start_date, policy_term_months=12,
                 policy_status="Active", policy_lapse_date=None):
        self.policy_id = policy_id
        self.age = age
        self.sex = sex
        self.migraine_history = migraine_history
        self.tension_type_headache_history = tension_type_headache_history
        self.typical_consumption_speed = typical_consumption_speed
        self.favourite_trigger = favourite_trigger
        self.underwriting_base = underwriting_base
        self.plan_name = plan_name
        self.annual_premium = usd(annual_premium)
        self.policy_start_date = policy_start_date
        self.policy_term_months = policy_term_months
        self.policy_status = policy_status
        self.policy_lapse_date = policy_lapse_date
        self.events = []

    # -- terms, from the plan rather than stored twice -------------------

    @property
    def plan(self):
        return COVERAGE_PLANS[self.plan_name]

    @property
    def coverage_limit(self):
        return self.plan.coverage_limit_per_incident

    @property
    def deductible(self):
        return self.plan.deductible_per_incident

    @property
    def underwriting_risk_score(self):
        """Scored from the recorded base, never stored.

        One source of truth: change a weight in `underwriting` and this moves,
        rather than quietly disagreeing with a number frozen at seed time.
        """
        return round(risk_score(
            self.age,
            self.migraine_history,
            self.tension_type_headache_history,
            self.typical_consumption_speed,
            self.favourite_trigger,
            self.underwriting_base), 1)

    @property
    def risk_tier(self):
        return risk_tier(self.underwriting_risk_score)

    @property
    def monthly_premium(self):
        #: Half-up on an exact division, so this cannot disagree with the
        #: same figure computed anywhere else. `170.10 / 12` is exactly
        #: `14.175`; rounding it is a decision, and the decision is written
        #: down rather than inherited from whichever library ran last.
        return round_cents(self.annual_premium / 12)

    @property
    def policy_end_date(self):
        return self.policy_start_date + timedelta(days=30 * self.policy_term_months)

    def is_in_force_on(self, when):
        """Was there cover on this date?

        Cover runs to the lapse date inclusive -- someone who lapses on the
        12th is still covered for the treat they ate that morning -- and it
        runs no further than the term at either end.
        """
        return self.no_cover_reason_on(when) is None

    def no_cover_reason_on(self, when):
        """Why there was no cover on this date, or None if there was.

        The lapse is tested first because it is the more specific fact: a
        policy that lapsed on the 10th and was claimed on the 20th lapsed,
        whether or not the term had also run out by then. What is left --
        before the policy was sold, or after the term ended without a lapse --
        is outside the term, and calling that a lapse would state something
        untrue about a policy that never lapsed. The distinction is the whole
        of it: CUJ-2 asks an agent to explain a refusal, and it can only do
        that from a reason that is actually the reason.
        """
        if self.policy_lapse_date is not None and when > self.policy_lapse_date:
            return REASON_POLICY_LAPSED
        if when < self.policy_start_date or when > self.policy_end_date:
            return REASON_OUTSIDE_TERM
        return None

    # -- what happened ---------------------------------------------------

    @property
    def claims(self):
        """Every claim filed, oldest first. Derived, never stored."""
        return [e.claim for e in self.events if e.claim is not None]

    @property
    def approved_claims(self):
        return [c for c in self.claims if c.is_approved]

    @property
    def brain_freeze_events(self):
        return [e for e in self.events if e.brain_freeze]

    @property
    def total_paid(self):
        return round_cents(sum((c.approved for c in self.approved_claims), ZERO))

    @property
    def claims_remaining_this_year(self):
        """How many more approvals the annual cap allows.

        Counted over the policy term, which is how the generator counted it.
        """
        return max(0, ANNUAL_CLAIM_LIMIT - len(self.approved_claims))

    @property
    def brain_freeze_rate(self):
        """How often a cold treat brought on a headache. Needs the non-events."""
        if not self.events:
            return None
        return len(self.brain_freeze_events) / len(self.events)

    @property
    def loss_ratio(self):
        """Paid out over premium collected. Above 1.0 and we are losing money."""
        if not self.annual_premium:
            return None
        # A ratio is not money, so it is published as a float -- but it is
        # rounded half-up rather than by bare `round()`, which is half-up in
        # the database and banker's outside it.
        return float(round_half_up(self.total_paid / self.annual_premium, 3))

    def add_event(self, event):
        """Add an event, in order, not at the end.

        Appending was enough while events only arrived from the CSV, which is
        already sorted. It is not enough once the app files a claim: that adds
        an event dated TODAY to a policy whose seeded events run into 2027, so
        an appended event belongs in the middle of the history and would
        otherwise be shown last.

        Sorting at load time and appending afterwards means the guarantee
        holds until the moment someone uses the demo, which is the worst
        possible time for it to stop holding.
        """
        key = event_order(event)
        position = len(self.events)
        for index, existing in enumerate(self.events):
            if event_order(existing) > key:
                position = index
                break
        self.events.insert(position, event)
        return event

    def __repr__(self):
        return "<Policyholder %s age %s %s/%s %d events>" % (
            self.policy_id, self.age, self.plan_name, self.risk_tier, len(self.events))


class SavedQuote:
    """A quote that was given, kept as an object rather than as a form post.

    Not `Quote` -- that name belongs to the NamedTuple `brainfreeze.quote()`
    hands back, which is a price worked out and returned. This is the one that
    is kept: it has an identity, an address in the web app, and a record of
    which policy it turned into.

    WHAT IT KEEPS AND WHAT IT DERIVES, WHICH IS THE ARGUMENT WORTH HAVING

    It keeps everything: the five answers, the score, the reasoning behind the
    score, and all three prices. That is the opposite of
    `Policyholder.underwriting_risk_score`, which is derived on purpose so that
    changing a weight moves it rather than leaving a number frozen at seed
    time -- and the difference is not an inconsistency.

    A quote is a promise made on a date. A policy sold from one has to be sold
    at the figure the customer was shown, and a re-opened quote that had
    quietly re-priced itself would be the same round-trip the hidden form
    fields were, with the state going through the rules instead of through the
    browser. A policy's score, by contrast, is a statement about a person and
    should be true today.

    IT HOLDS MONEY, SO IT HOLDS DECIMAL

    Twelve figures of it -- annual, monthly, limit and deductible for each of
    the three plans -- and every one arrives through `usd`, which refuses a
    float outright. Money enters the model at `Claim`, at `Policyholder` and
    here, and nowhere else; those three calls are the whole guarantee that
    none of it is a float. A committed Decimal keeps its value, its ordering
    and its equality, measured; what it does not keep is its trailing zero, so
    nothing here may print one with `str()`.
    """

    #: Which policy this quote became, once someone took it up. A class
    #: attribute as well as an instance one, declared before this class was
    #: ever committed, which is the only moment a default can be added for
    #: free -- see `Claim.rule` above and docs/prd-corrections.md correction 5.
    policy_id = None

    def __init__(self, quote_id, quoted_on, age, migraine_history,
                 tension_type_headache_history, typical_consumption_speed,
                 favourite_trigger, score, risk_tier, breakdown, plans,
                 policy_id=None):
        self.quote_id = quote_id
        self.quoted_on = quoted_on

        #: The five answers, spelled exactly as `underwriting.quote` and
        #: `Policyholder` both spell them. See the `answers` property.
        self.age = age
        self.migraine_history = migraine_history
        self.tension_type_headache_history = tension_type_headache_history
        self.typical_consumption_speed = typical_consumption_speed
        self.favourite_trigger = favourite_trigger

        #: A score is not money and is honestly a float; so are the points in
        #: the breakdown. Only the plans below go through `usd`.
        self.score = score
        self.risk_tier = risk_tier
        self.breakdown = [(label, points) for label, points in breakdown]

        priced = {}
        for name in plans:
            plan = plans[name]
            priced[name] = {
                "annual": usd(plan["annual"]),
                "monthly": usd(plan["monthly"]),
                "limit": usd(plan["limit"]),
                "deductible": usd(plan["deductible"]),
            }
        self.plans = priced

        if policy_id is not None:
            self.policy_id = policy_id

    @property
    def answers(self):
        """The five answers, keyed the way both callers want them.

        `brainfreeze.quote(**saved.answers)` re-prices it and
        `Policyholder(..., **saved.answers)` sells it, with nothing restated
        in between. Restating them is what the hidden fields were.
        """
        return dict(
            age=self.age,
            migraine_history=self.migraine_history,
            tension_type_headache_history=self.tension_type_headache_history,
            typical_consumption_speed=self.typical_consumption_speed,
            favourite_trigger=self.favourite_trigger,
        )

    @property
    def is_accepted(self):
        return self.policy_id is not None

    def __repr__(self):
        # `.get`, because a repr that raises is worse than a repr that says
        # less -- and `format_usd(None)` is already "--".
        standard = self.plans.get("Standard")
        return "<SavedQuote %s %s %s%s>" % (
            self.quote_id, self.risk_tier,
            format_usd(standard["annual"] if standard else None),
            " -> %s" % self.policy_id if self.policy_id else "")


class Book:
    """The whole book of business -- the one object the database root holds.

    Everything else hangs off this, so a notebook or an agent needs exactly one
    lookup to get started:

        import gemdb
        book = gemdb.root["brainfreeze"]
        book.policies["BF-100539"].total_paid
    """

    def __init__(self):
        self.policies = {}
        #: Quotes given, by quote id. A separate mapping rather than a
        #: policy's field, because most quotes never become a policy -- and
        #: deliberately not in `policies`, which `len(self)` counts and
        #: `verify_book.py` pins at 900.
        self.quotes = {}

    def add(self, policyholder):
        self.policies[policyholder.policy_id] = policyholder
        return policyholder

    def add_quote(self, a_quote):
        """Keep a quote. It is not a policy and is counted as neither.

        A Book committed before this field existed has no `quotes` slot of its
        own, and declaring one on the class now would not reach it: editing a
        class compiles a DIFFERENT class and instances keep the one they were
        made under (findings/03_class_identity.py, docs/prd-corrections.md
        correction 5). So this raises AttributeError on an old book rather
        than pretending, and the fix is the documented pair -- `gemdb
        redeploy.py` to give the database the new code, then `gemdb tools/seed.py`
        to rebuild the book under it.
        """
        self.quotes[a_quote.quote_id] = a_quote
        return a_quote

    def __len__(self):
        return len(self.policies)

    def __iter__(self):
        return iter(self.policies.values())

    def __getitem__(self, policy_id):
        return self.policies[policy_id]

    @property
    def events(self):
        return [e for p in self for e in p.events]

    @property
    def claims(self):
        return [c for p in self for c in p.claims]

    @property
    def total_premium(self):
        return round_cents(sum((p.annual_premium for p in self), ZERO))

    @property
    def total_paid(self):
        return round_cents(sum((p.total_paid for p in self), ZERO))

    @property
    def loss_ratio(self):
        """Paid over premium for the whole book, as a float.

        Summing 900 exact premiums and then dividing once is the right order
        anyway, and with Decimal the sum is exact rather than 900 roundings
        deep. See `analysis.loss_ratio_by_tier` for why this is never an
        average of ratios.
        """
        if not self.total_premium:
            return None
        return float(round_half_up(self.total_paid / self.total_premium, 3))

    def __repr__(self):
        return "<Book %d policies, %d events, loss ratio %s>" % (
            len(self.policies), len(self.events), self.loss_ratio)
