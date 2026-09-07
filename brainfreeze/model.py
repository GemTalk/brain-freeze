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

from datetime import date, timedelta

from .adjudication import ANNUAL_CLAIM_LIMIT
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

    def __init__(self, claim_id, requested, approved, status, reason=None,
                 flavour=None, toppings=None):
        self.claim_id = claim_id
        self.requested = requested
        self.approved = approved
        self.status = status
        self.reason = reason
        if flavour is not None:
            self.flavour = flavour
        if toppings is not None:
            self.toppings = tuple(toppings)

    @property
    def is_approved(self):
        return self.status == "Approved"

    def __repr__(self):
        return "<Claim %s %s $%.2f>" % (self.claim_id, self.status, self.approved)


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
        self.annual_premium = annual_premium
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
        return round(self.annual_premium / 12, 2)

    @property
    def policy_end_date(self):
        return self.policy_start_date + timedelta(days=30 * self.policy_term_months)

    def is_in_force_on(self, when):
        """Was there cover on this date?

        Cover runs to the lapse date inclusive -- someone who lapses on the
        12th is still covered for the treat they ate that morning.
        """
        if self.policy_lapse_date is None:
            return True
        return when <= self.policy_lapse_date

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
        return round(sum(c.approved for c in self.approved_claims), 2)

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
        return round(self.total_paid / self.annual_premium, 3)

    def add_event(self, event):
        self.events.append(event)
        return event

    def __repr__(self):
        return "<Policyholder %s age %s %s/%s %d events>" % (
            self.policy_id, self.age, self.plan_name, self.risk_tier, len(self.events))


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

    def add(self, policyholder):
        self.policies[policyholder.policy_id] = policyholder
        return policyholder

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
        return round(sum(p.annual_premium for p in self), 2)

    @property
    def total_paid(self):
        return round(sum(p.total_paid for p in self), 2)

    @property
    def loss_ratio(self):
        if not self.total_premium:
            return None
        return round(self.total_paid / self.total_premium, 3)

    def __repr__(self):
        return "<Book %d policies, %d events, loss ratio %s>" % (
            len(self.policies), len(self.events), self.loss_ratio)
