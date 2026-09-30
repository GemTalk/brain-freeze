"""The objects that live in the database.

A policyholder holds every cold treat they recorded, in order, and each may
or may not have a claim attached. Not a list of *claims*: most cold treats
hurt nobody, and those are the denominator. Without them "how often does a
slushie cause brain freeze" is not a question the data can answer.

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

    #: Which rule refused this claim, as a stable identifier, alongside
    #: the sentence in `reason`. A class attribute as well as an instance one:
    #: a claim written before the field existed has no slot of its own, and
    #: reads the default through the class. Code reading a whole book uses
    #: `getattr(claim, "rule", None)` anyway, as `analysis.denial_rules`
    #: does; it costs nothing.
    rule = None

    def __init__(self, claim_id, requested, approved, status, reason=None,
                 rule=None):
        self.claim_id = claim_id
        #: Through `usd`, which refuses a float outright. Money enters the
        #: model only here, at Policyholder and at SavedQuote.
        self.requested = usd(requested)
        self.approved = usd(approved)
        self.status = status
        self.reason = reason
        if rule is not None:
            self.rule = rule

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

    The date alone is not a total order: 37 policies in the committed data
    record two cold treats on the same day, and a stable date-only sort would
    leave those ties in CSV row order. `event_id` breaks them. It is unique,
    and zero-padded (`EVT-000001`, the series the web app also mints from) so
    string order is numeric order. Shuffle the file and every policy loads in
    the same order.
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
        """Scored from the recorded base, never stored, so changing a weight
        in `underwriting` moves it."""
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
        #: Half-up on an exact division, so this agrees with the same figure
        #: computed anywhere else: `170.10 / 12` is exactly `14.175`.
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
        whether or not the term had also run out. What is left -- before the
        policy was sold, or after a term that ended without a lapse -- is
        outside the term, and must not be called a lapse. An agent explaining
        a refusal can only be as right as this reason.
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
        # A ratio is not money, so it is published as a float -- rounded
        # half-up, as money is, rather than half to even.
        return float(round_half_up(self.total_paid / self.annual_premium, 3))

    def add_event(self, event):
        """Add an event, in order, not at the end.

        The app files claims dated today on policies whose seeded events run
        into 2027, so a new event usually belongs in the middle of the
        history. Appending would show it last.
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

    Not `Quote` -- that is the NamedTuple `brainfreeze.quote()` returns, a
    price worked out and handed back. This one is kept: it has an identity,
    an address in the web app, and a record of which policy it became.

    It stores everything -- the five answers, the score, its breakdown and all
    three prices -- where `Policyholder.underwriting_risk_score` is derived.
    That is deliberate: a quote is a promise made on a date, and a policy sold
    from it must be sold at the figure the customer was shown. A policy's
    score is a statement about a person and should be true today.

    Every price arrives through `usd`, which refuses a float. Never print one
    with `str()`; see `brainfreeze.money`.
    """

    #: Which policy this quote became, once someone took it up. A class
    #: attribute as well as an instance one, so a quote that was never taken
    #: up reads None -- the same rule as `Claim.rule` above.
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
        """The five answers, keyed the way both callers want them:
        `brainfreeze.quote(**saved.answers)` re-prices it and
        `Policyholder(..., **saved.answers)` sells it.
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
        #: Quotes given, by quote id. Separate from `policies`, because most
        #: quotes never become a policy and `len(self)` counts policies.
        self.quotes = {}

    def add(self, policyholder):
        self.policies[policyholder.policy_id] = policyholder
        return policyholder

    def add_quote(self, a_quote):
        """Keep a quote. It is not a policy and is counted as neither.

        A Book committed before `quotes` existed has no such slot, and there
        is deliberately no class-level `quotes = {}` to cover it: a mutable
        class default would be shared by every Book that fell through to it.
        So this raises on an old book; the fix is `gemdb tools/load.py` for
        the code, then `gemdb tools/seed.py` to rebuild the book.
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

        Sum, then divide once: never an average of ratios (see
        `analysis._loss_ratio_grouped`).
        """
        if not self.total_premium:
            return None
        return float(round_half_up(self.total_paid / self.total_premium, 3))

    def __repr__(self):
        return "<Book %d policies, %d events, loss ratio %s>" % (
            len(self.policies), len(self.events), self.loss_ratio)
