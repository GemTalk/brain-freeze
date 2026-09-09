"""Brain Freeze Insurance, as a web app running inside the database.

    gemdb app.py            # serves on http://127.0.0.1:5000/

Start it from the project directory. `sys.path[0]` is the script's directory,
and an import that cannot find `brainfreeze/` on disk resolves out of the
database to whatever class was last compiled there -- silently. See "Editing a
class does not update the database" in PLAN.md.

WHAT IS AND IS NOT HERE

There is no ORM, no schema, no migration and no serializer, because there is
nothing to map: `gemdb.root["brainfreeze"]` is a Book of Policyholders and a
handler reads and writes those objects directly. Creating a policy is
`book.add(Policyholder(...))` followed by `gemdb.commit()`. That is the whole
persistence layer, and its absence is the point of the demo.

Every number on every screen comes from the `brainfreeze` package. A handler
that worked out a premium or a payout for itself would be a bug: two copies of
"what does this claim pay" drift by the second demo, and CUJ-2 asks an agent
to explain a refusal -- an answer it cannot give if the app and the data
disagree about the rules.

THREE CONSTRAINTS FROM GRAIL, ALL FOUND FIRST BY grail_rest_demo/app.py

1. `threaded=False`. Grail renders each Jinja template in a forked green
   thread, and the threaded dev server's per-request ContextVar cannot span
   those threads, so `url_for` inside a template cannot see the active
   request. One CPU per gem means threading buys nothing anyway.
2. One request per connection, via CloseAfterResponseHandler. A
   single-threaded server parked reading a kept-alive connection cannot accept
   the next one, so a second tab or a favicon fetch hangs everything.
3. Inline templates only. `render_template_string` is exercised in Grail's own
   suite; file-based `render_template` is not. Templates are module constants.

Every write is a POST that mutates, commits and redirects, so a refresh never
re-submits.
"""

from datetime import date

from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    url_for,
)
from werkzeug.serving import WSGIRequestHandler

import gemdb

import brainfreeze
from brainfreeze.model import Claim, Event, Policyholder

ROOT_KEY = "brainfreeze"


class CloseAfterResponseHandler(WSGIRequestHandler):
    """One request per connection -- see constraint 2 in the module docstring."""

    def handle_one_request(self):
        try:
            self.raw_requestline = self.rfile.readline(65537)
        except OSError:
            self.close_connection = True
            return
        if not self.raw_requestline:
            self.close_connection = True
            return
        if not self.parse_request():
            return
        self.close_connection = True
        self.run_wsgi()


# -- turning what a person can answer into what the model needs -------------
# The claimant describes an episode in words; the model wants numbers. These
# are the translation, and they live here rather than in `brainfreeze` because
# they are the vocabulary of the form, not a rule. Nobody owns a thermometer
# for this, so a band is the honest question.

COLD_BANDS = [
    ("Straight from the freezer", -12.0),
    ("Iced", -4.0),
    ("Fridge-cold", 2.0),
    ("Cool", 8.0),
]
PORTION_BANDS = [
    ("A few sips", 40.0),
    ("Small", 100.0),
    ("Regular", 180.0),
    ("A lot", 320.0),
]
SPEED_BANDS = [
    ("Slowly", "slow"),
    ("About normal", "moderate"),
    ("All at once", "fast"),
]
DURATION_BANDS = [
    ("Under 30 seconds", 20.0),
    ("Half a minute to two", 70.0),
    ("Two to ten minutes", 300.0),
    ("Longer than ten", 700.0),
]
PAIN_LOCATIONS = ["Forehead", "Temple", "Back of the head", "All over"]
PAIN_QUALITIES = ["Stabbing", "Pulling", "Dull and pressing"]

#: CUJ-4. Added after 900 policies and 4,993 episodes were already committed.
#: Nothing was migrated and nothing was rewritten: `Claim.flavour` and
#: `Claim.toppings` are class attributes with defaults, so the 2,172 claims
#: filed before these questions existed have no slot of their own and read
#: None and () through the class. That is the entire migration.
FLAVOURS = ["Vanilla", "Chocolate", "Strawberry", "Mint choc chip",
            "Cookie dough", "Something else"]
TOPPINGS = ["Sprinkles", "Hot fudge", "Whipped cream", "Nuts", "Cherry"]

TRIGGERS = brainfreeze.TRIGGER_TYPES

#: Policyholders per page on the picker.
PAGE = 25


def _band(bands, label, default=None):
    """The value for a band's label, or the default when it is not one of ours."""
    for name, value in bands:
        if name == label:
            return value
    if default is not None:
        return default
    return bands[0][1]


def book():
    return gemdb.root[ROOT_KEY]


def cover_state(policy, today):
    """How to describe this policy's cover, as of a date.

    `policy_status` records the fate of a policy over its whole term, and the
    sample book's terms run either side of the present -- of 217 policies
    marked Lapsed, only 53 have actually reached their lapse date. So a screen
    that reads the stored status calls a policy lapsed while it is still
    paying claims. Compare against the date instead and say which it is.

    The term counts too, at both ends: 147 of the 900 policies have not
    started yet today, and calling those "Active" says cover is running when
    a claim filed against them would be refused.
    """
    if policy.is_in_force_on(today):
        if policy.policy_lapse_date is None:
            return ("Active", "ok")
        return ("Lapses %s" % policy.policy_lapse_date, "tag")
    if policy.no_cover_reason_on(today) == brainfreeze.REASON_POLICY_LAPSED:
        return ("Lapsed %s" % policy.policy_lapse_date, "no")
    if today < policy.policy_start_date:
        return ("Starts %s" % policy.policy_start_date, "tag")
    return ("Term ended %s" % policy.policy_end_date, "no")


def _next_id(existing, prefix, width, start):
    """The next free identifier in a series, given the ones already used."""
    highest = start - 1
    for identifier in existing:
        try:
            highest = max(highest, int(identifier.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return "%s-%0*d" % (prefix, width, highest + 1)


def create_app():
    app = Flask(__name__)

    # -- the picker: stands in for the sign-in this demo does not have ----

    @app.route("/")
    def index():
        # A page at a time. Rendering all 900 takes the best part of a minute
        # -- Grail runs each Jinja template in a forked green thread, and 900
        # rows of it is not what that is for. The count is the point, not the
        # scroll, so the total is stated and the table is a window onto it.
        today = date.today()
        everyone = sorted(book(), key=lambda p: p.policy_id)

        wanted = (request.args.get("policy") or "").strip().upper()
        if wanted:
            match = [p for p in everyone if wanted in p.policy_id]
            if len(match) == 1:
                return redirect(url_for("history",
                                        policy_id=match[0].policy_id))
            everyone, start = match, 0
        else:
            try:
                start = max(0, int(request.args.get("from", 0)))
            except ValueError:
                start = 0

        window = everyone[start:start + PAGE]
        rows = [(p,) + cover_state(p, today) for p in window]
        return render_template_string(
            PICKER, rows=rows, total=len(book()), shown=len(everyone),
            start=start, page=PAGE, wanted=wanted)

    # -- the quote flow ---------------------------------------------------

    @app.route("/quote")
    def quote_form():
        return render_template_string(
            QUOTE_FORM, triggers=TRIGGERS, speeds=SPEED_BANDS)

    def _answers():
        """The five questions. Note what is absent: FR-5.2 asks for sex, and
        it carries no weight in the risk model, so the form would pose a
        question that changes nothing."""
        return dict(
            age=int(request.form.get("age", 11)),
            migraine_history=request.form.get("migraine") == "yes",
            tension_type_headache_history=request.form.get("tth") == "yes",
            typical_consumption_speed=request.form.get("speed", "moderate"),
            favourite_trigger=request.form.get("trigger", "ice cream"),
        )

    @app.route("/quote", methods=["POST"])
    def quote_result():
        answers = _answers()
        offer = brainfreeze.quote(**answers)
        return render_template_string(PLANS, offer=offer, answers=answers)

    @app.route("/policies", methods=["POST"])
    def create_policy():
        answers = _answers()
        offer = brainfreeze.quote(**answers)
        plan_name = request.form.get("plan", "Standard")

        the_book = book()
        policy = Policyholder(
            policy_id=_next_id([p.policy_id for p in the_book], "BF", 6, 100000),
            sex=None,
            underwriting_base=brainfreeze.BASE_RISK,
            plan_name=plan_name,
            annual_premium=offer.plans[plan_name]["annual"],
            policy_start_date=date.today(),
            **answers)
        the_book.add(policy)
        gemdb.commit()
        return redirect(url_for("history", policy_id=policy.policy_id))

    # -- one policy's history ---------------------------------------------

    def _policy_or_404(policy_id):
        try:
            return book()[policy_id]
        except KeyError:
            abort(404)

    @app.route("/policies/<policy_id>")
    def history(policy_id):
        policy = _policy_or_404(policy_id)
        today = date.today()
        label, css = cover_state(policy, today)
        return render_template_string(
            HISTORY, p=policy, cover=label, cover_css=css,
            limit=brainfreeze.ANNUAL_CLAIM_LIMIT)

    # -- filing a claim ----------------------------------------------------

    def _warnings(policy, today):
        """What the form should say before anyone fills it in.

        Both of these would otherwise only be discovered by filing and being
        refused, and the lapse is the more confusing one to receive silently.

        Which absence of cover it is comes from the model, so the warning on
        the form and the reason on the refusal cannot disagree -- and so a
        policy that has not started yet is not told it lapsed on None.
        """
        notes = []
        no_cover = policy.no_cover_reason_on(today)
        if no_cover == brainfreeze.REASON_POLICY_LAPSED:
            notes.append(
                "Cover on this policy ended on %s. Anything filed now is "
                "refused." % policy.policy_lapse_date)
        elif no_cover is not None:
            if today < policy.policy_start_date:
                notes.append(
                    "Cover on this policy does not start until %s. Anything "
                    "filed now is refused." % policy.policy_start_date)
            else:
                notes.append(
                    "The term on this policy ended on %s. Anything filed now "
                    "is refused." % policy.policy_end_date)
        elif policy.claims_remaining_this_year == 0:
            notes.append(
                "This policy has used all %d approvals for the year. A new "
                "claim is refused until it renews."
                % brainfreeze.ANNUAL_CLAIM_LIMIT)
        return notes

    @app.route("/policies/<policy_id>/claims/new")
    def claim_form(policy_id):
        policy = _policy_or_404(policy_id)
        return render_template_string(
            CLAIM_FORM, p=policy, triggers=TRIGGERS, colds=COLD_BANDS,
            portions=PORTION_BANDS, speeds=SPEED_BANDS,
            durations=DURATION_BANDS, locations=PAIN_LOCATIONS,
            qualities=PAIN_QUALITIES, flavours=FLAVOURS, toppings=TOPPINGS,
            warnings=_warnings(policy, date.today()))

    @app.route("/policies/<policy_id>/claims", methods=["POST"])
    def file_claim(policy_id):
        policy = _policy_or_404(policy_id)
        today = date.today()

        pain = float(request.form.get("pain", 5))
        duration = _band(DURATION_BANDS, request.form.get("duration"))

        # The claimant never enters a figure. This derives it, so two people
        # who describe the same episode get the same number.
        requested = brainfreeze.assess_amount(pain, duration)

        decision = brainfreeze.adjudicate(
            requested,
            policy.coverage_limit,
            policy.deductible,
            len(policy.approved_claims),
            policy_in_force=policy.is_in_force_on(today),
            no_cover_reason=policy.no_cover_reason_on(today))

        the_book = book()
        claim = Claim(
            claim_id=_next_id([c.claim_id for c in the_book.claims],
                              "CLM", 6, 1),
            requested=requested,
            approved=decision.amount,
            status=decision.status,
            reason=decision.reason,
            flavour=request.form.get("flavour") or None,
            toppings=request.form.getlist("toppings") or None)
        policy.add_event(Event(
            event_id=_next_id([e.event_id for e in the_book.events],
                              "EVT", 6, 1),
            event_date=today,
            trigger=request.form.get("trigger", "ice cream"),
            temperature_c=_band(COLD_BANDS, request.form.get("cold")),
            portion_ml=_band(PORTION_BANDS, request.form.get("portion")),
            consumption_speed=_band(SPEED_BANDS, request.form.get("speed"),
                                    default="moderate"),
            brain_freeze=True,
            duration_sec=duration,
            pain_intensity=pain,
            pain_location=request.form.get("location"),
            pain_quality=request.form.get("quality"),
            claim=claim))
        gemdb.commit()

        return redirect(url_for("decision", policy_id=policy.policy_id,
                                claim_id=claim.claim_id))

    @app.route("/policies/<policy_id>/claims/<claim_id>")
    def decision(policy_id, claim_id):
        policy = _policy_or_404(policy_id)
        for event in policy.events:
            if event.claim is not None and event.claim.claim_id == claim_id:
                return render_template_string(
                    DECISION, p=policy, e=event, c=event.claim)
        abort(404)

    return app


def serve(host="127.0.0.1", port=5000):
    create_app().run(host=host, port=port, threaded=False,
                     request_handler=CloseAfterResponseHandler)



# -- templates, as module constants (constraint 3) --------------------------

_STYLE = """
<style>
  body { font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
         max-width: 46rem; margin: 2.5rem auto; padding: 0 1.2rem;
         color: #16202a; background: #f7f8fa; line-height: 1.5; }
  a { color: #1a6ee0; }
  h1 { font-size: 1.5rem; margin-bottom: .2rem; }
  .sub { color: #667; margin-top: 0; }
  .card { background: #fff; border-radius: 14px; padding: 1.1rem 1.3rem;
          margin: .8rem 0; box-shadow: 0 1px 2px rgba(0,0,0,.07); }
  .row { display: flex; justify-content: space-between; gap: 1rem;
         align-items: baseline; }
  .tag { font-size: .78rem; font-weight: 700; padding: .15rem .5rem;
         border-radius: 999px; background: #eef2f6; color: #667; }
  .ok { background: #e3f5ea; color: #17683a; }
  .no { background: #fdeceb; color: #97231b; }
  .warn { background: #fff6e5; border-left: 4px solid #e0a021;
          padding: .8rem 1rem; border-radius: 8px; margin: .6rem 0; }
  .num { font-variant-numeric: tabular-nums; }
  .big { font-size: 1.9rem; font-weight: 800; }
  .muted { color: #7a8798; font-size: .85rem; }
  fieldset { border: 0; padding: 0; margin: 0 0 1.1rem; }
  legend { font-weight: 700; padding: 0; margin-bottom: .35rem; }
  label.opt { display: inline-block; margin: .15rem .3rem .15rem 0; }
  button { font: inherit; font-weight: 700; padding: .55rem 1.1rem;
           border: 0; border-radius: 9px; background: #1a6ee0; color: #fff;
           cursor: pointer; }
  table { border-collapse: collapse; width: 100%; }
  td, th { text-align: left; padding: .4rem .3rem;
           border-bottom: 1px solid #eef1f4; }
  th { font-size: .78rem; text-transform: uppercase; color: #7a8798; }
</style>
"""

PICKER = _STYLE + """
<h1>Brain Freeze Insurance</h1>
<p class="sub">{{ total }} policyholders, live in the database.
   <a href="{{ url_for('quote_form') }}">Get a quote</a></p>
<form method="get" action="{{ url_for('index') }}" class="card">
  <label>Go to a policy
    <input type="text" name="policy" value="{{ wanted }}"
           placeholder="BF-100539" size="12"></label>
  <button type="submit">Find</button>
  {% if wanted %}<a href="{{ url_for('index') }}">clear</a>{% endif %}
</form>
<div class="card">
<table>
  <tr><th>Policy</th><th>Plan</th><th>Band</th><th>Status</th>
      <th>Claims</th><th>Paid</th></tr>
  {% for p, label, css in rows %}
  <tr>
    <td><a href="{{ url_for('history', policy_id=p.policy_id) }}"
           class="num">{{ p.policy_id }}</a></td>
    <td>{{ p.plan_name }}</td>
    <td class="num">{{ p.risk_tier }}, {{ p.underwriting_risk_score }}</td>
    <td><span class="tag {{ css }}">{{ label }}</span></td>
    <td class="num">{{ p.approved_claims|length }}/{{ p.claims|length }}</td>
    <td class="num">${{ '%.2f'|format(p.total_paid) }}</td>
  </tr>
  {% endfor %}
</table>
{% if not wanted %}
<p class="muted">
  {% if start > 0 %}
  <a href="{{ url_for('index', **{'from': start - page}) }}">&larr; previous</a>
  {% endif %}
  Showing {{ start + 1 }}&ndash;{{ [start + page, shown]|min }} of {{ shown }}.
  {% if start + page < shown %}
  <a href="{{ url_for('index', **{'from': start + page}) }}">next &rarr;</a>
  {% endif %}
</p>
{% elif not rows %}
<p class="muted">Nothing matches &ldquo;{{ wanted }}&rdquo;.</p>
{% endif %}
</div>
"""

QUOTE_FORM = _STYLE + """
<h1>What would cover cost?</h1>
<p class="sub">Five questions. We work the price out from the answers.</p>
<form method="post" action="{{ url_for('quote_result') }}" class="card">
  <fieldset><legend>How old are they?</legend>
    <input type="number" name="age" value="11" min="5" max="19"></fieldset>
  <fieldset><legend>Diagnosed with migraine?</legend>
    <label class="opt"><input type="radio" name="migraine" value="no" checked> No</label>
    <label class="opt"><input type="radio" name="migraine" value="yes"> Yes</label></fieldset>
  <fieldset><legend>Diagnosed with tension headaches?</legend>
    <label class="opt"><input type="radio" name="tth" value="no" checked> No</label>
    <label class="opt"><input type="radio" name="tth" value="yes"> Yes</label></fieldset>
  <fieldset><legend>How fast do they usually eat something cold?</legend>
    {% for label, value in speeds %}
    <label class="opt"><input type="radio" name="speed" value="{{ value }}"
      {% if value == 'moderate' %}checked{% endif %}> {{ label }}</label>
    {% endfor %}</fieldset>
  <fieldset><legend>Favourite cold treat</legend>
    {% for t in triggers %}
    <label class="opt"><input type="radio" name="trigger" value="{{ t }}"
      {% if loop.first %}checked{% endif %}> {{ t }}</label>
    {% endfor %}</fieldset>
  <button type="submit">See the price</button>
</form>
"""

PLANS = _STYLE + """
<h1>Three ways to cover it</h1>
<p class="sub">Risk band <strong>{{ offer.tier }}</strong>,
   scored <span class="num">{{ offer.score }}</span>.</p>

<div class="card">
  <strong>How that score was reached</strong>
  <table>
    {% for label, points in offer.breakdown %}
    <tr><td>{{ label }}</td>
        <td class="num" style="text-align:right">{{ '%+.1f'|format(points) }}</td></tr>
    {% endfor %}
  </table>
</div>

{% for name, plan in offer.plans.items() %}
<form method="post" action="{{ url_for('create_policy') }}" class="card">
  <div class="row">
    <div>
      <strong>{{ name }}</strong>
      <div class="muted">${{ '%.2f'|format(plan.limit) }} an episode,
        ${{ '%.2f'|format(plan.deductible) }} deductible</div>
    </div>
    <div style="text-align:right">
      <div class="big num">${{ '%.2f'|format(plan.annual) }}</div>
      <div class="muted">a year &middot; ${{ '%.2f'|format(plan.monthly) }} a month</div>
    </div>
  </div>
  {% for key, value in answers.items() %}
  <input type="hidden" name="{{
    {'migraine_history':'migraine','tension_type_headache_history':'tth',
     'typical_consumption_speed':'speed','favourite_trigger':'trigger',
     'age':'age'}[key] }}" value="{{
    'yes' if value is sameas true else ('no' if value is sameas false else value) }}">
  {% endfor %}
  <input type="hidden" name="plan" value="{{ name }}">
  <button type="submit">Take out {{ name }}</button>
</form>
{% endfor %}
"""

HISTORY = _STYLE + """
<h1 class="num">{{ p.policy_id }}</h1>
<p class="sub">{{ p.plan_name }} &middot; {{ p.risk_tier }} band,
  <span class="num">{{ p.underwriting_risk_score }}</span> &middot;
  ${{ '%.2f'|format(p.coverage_limit) }} an episode,
  ${{ '%.2f'|format(p.deductible) }} deductible &middot;
  <span class="tag {{ cover_css }}">{{ cover }}</span>
</p>

<div class="card row">
  <div><div class="big num">{{ p.events|length }}</div><div class="muted">cold treats</div></div>
  <div><div class="big num">{{ p.brain_freeze_events|length }}</div><div class="muted">gave a headache</div></div>
  <div><div class="big num">{{ p.claims|length }}</div><div class="muted">claims sent</div></div>
  <div><div class="big num">${{ '%.2f'|format(p.total_paid) }}</div><div class="muted">paid out</div></div>
  <div><div class="big num">{{ p.approved_claims|length }}/{{ limit }}</div><div class="muted">claims used</div></div>
</div>

<p><a href="{{ url_for('claim_form', policy_id=p.policy_id) }}">File a claim</a>
   &middot; <a href="{{ url_for('index') }}">All policyholders</a></p>

<div class="card">
  <strong>Every cold treat on record</strong>
  {% if not p.events %}
  <p class="muted">Nothing yet. When something cold causes trouble, file it
     and it will appear here.</p>
  {% else %}
  <table>
    <tr><th>Date</th><th>Treat</th><th>Claim</th><th>Outcome</th></tr>
    {% for e in p.events %}
    <tr>
      <td class="num">{{ e.event_date }}</td>
      <td>{{ e.trigger }}{% if not e.brain_freeze %}
          <span class="muted">&middot; no headache</span>{% endif %}</td>
      <td class="num">{{ e.claim.claim_id if e.claim else '' }}</td>
      <td>{% if not e.claim %}<span class="muted">not claimed</span>
          {% elif e.claim.is_approved %}
            <span class="num">${{ '%.2f'|format(e.claim.approved) }}</span>
          {% else %}<span class="tag no">{{ e.claim.reason }}</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
</div>
<p class="muted">The treats that caused no headache are here too. They are the
  denominator &mdash; without them, how often a slushie causes brain freeze is
  not a question the data can answer.</p>
"""

CLAIM_FORM = _STYLE + """
<h1>What happened?</h1>
<p class="sub">Tell us about the episode. We work the money out from your
  answers &mdash; there is no figure to type in.</p>

{% for note in warnings %}<div class="warn">{{ note }}</div>{% endfor %}

<form method="post" action="{{ url_for('file_claim', policy_id=p.policy_id) }}"
      class="card">
  <fieldset><legend>What did they have?</legend>
    {% for t in triggers %}
    <label class="opt"><input type="radio" name="trigger" value="{{ t }}"
      {% if loop.first %}checked{% endif %}> {{ t }}</label>{% endfor %}</fieldset>
  <fieldset><legend>How cold was it?</legend>
    {% for label, value in colds %}
    <label class="opt"><input type="radio" name="cold" value="{{ label }}"
      {% if loop.first %}checked{% endif %}> {{ label }}</label>{% endfor %}
    <div class="muted">A band, not a reading &mdash; nobody owns a thermometer
      for this.</div></fieldset>
  <fieldset><legend>How much of it?</legend>
    {% for label, value in portions %}
    <label class="opt"><input type="radio" name="portion" value="{{ label }}"
      {% if loop.index0 == 2 %}checked{% endif %}> {{ label }}</label>{% endfor %}</fieldset>
  <fieldset><legend>How fast?</legend>
    {% for label, value in speeds %}
    <label class="opt"><input type="radio" name="speed" value="{{ label }}"
      {% if loop.index0 == 1 %}checked{% endif %}> {{ label }}</label>{% endfor %}</fieldset>
  <fieldset><legend>How bad was it? (0&ndash;10)</legend>
    <input type="number" name="pain" value="5" min="0" max="10"></fieldset>
  <fieldset><legend>How long did it last?</legend>
    {% for label, value in durations %}
    <label class="opt"><input type="radio" name="duration" value="{{ label }}"
      {% if loop.index0 == 2 %}checked{% endif %}> {{ label }}</label>{% endfor %}</fieldset>
  <fieldset><legend>Where did it hurt?</legend>
    {% for l in locations %}
    <label class="opt"><input type="radio" name="location" value="{{ l }}"
      {% if loop.first %}checked{% endif %}> {{ l }}</label>{% endfor %}</fieldset>
  <fieldset><legend>What did it feel like?</legend>
    {% for q in qualities %}
    <label class="opt"><input type="radio" name="quality" value="{{ q }}"
      {% if loop.first %}checked{% endif %}> {{ q }}</label>{% endfor %}</fieldset>
  <fieldset><legend>Which flavour? <span class="tag">new</span></legend>
    {% for f in flavours %}
    <label class="opt"><input type="radio" name="flavour" value="{{ f }}"
      {% if loop.first %}checked{% endif %}> {{ f }}</label>{% endfor %}</fieldset>
  <fieldset><legend>Anything on top? <span class="tag">new</span></legend>
    {% for top in toppings %}
    <label class="opt"><input type="checkbox" name="toppings"
      value="{{ top }}"> {{ top }}</label>{% endfor %}
    <div class="muted">These two questions went in after 900 policies and
      4,993 episodes were already committed. No migration, nothing rewritten
      &mdash; older claims simply have no flavour.</div></fieldset>
  <button type="submit">Send the claim</button>
</form>
"""

DECISION = _STYLE + """
{% if c.is_approved %}
<h1>${{ '%.2f'|format(c.approved) }} is yours</h1>
{% else %}
<h1>Not this time</h1>
{% endif %}
<p class="sub num">{{ c.claim_id }} &middot; {{ e.trigger }}
  {%- if c.flavour %} ({{ c.flavour }}{% if c.toppings %},
    {{ c.toppings|join(', ')|lower }}{% endif %}){% endif %}
  &middot; {{ e.event_date }}</p>

<div class="card">
  <table>
    <tr><td>What we worked it out at</td>
        <td class="num" style="text-align:right">${{ '%.2f'|format(c.requested) }}</td></tr>
    {% if c.is_approved %}
    <tr><td>Trimmed to your ${{ '%.2f'|format(p.coverage_limit) }} episode cap</td>
        <td class="num" style="text-align:right">&minus;${{
          '%.2f'|format(c.requested - c.approved - p.deductible
                        if c.requested - c.approved - p.deductible > 0 else 0) }}</td></tr>
    <tr><td>Your deductible</td>
        <td class="num" style="text-align:right">&minus;${{ '%.2f'|format(p.deductible) }}</td></tr>
    {% else %}
    <tr><td colspan="2"><span class="tag no">{{ c.reason }}</span></td></tr>
    {% endif %}
    <tr><td><strong>Paid to you</strong></td>
        <td class="num" style="text-align:right">
          <strong>${{ '%.2f'|format(c.approved) }}</strong></td></tr>
  </table>
</div>

<p class="muted">It goes on the record either way &mdash;
  <a href="{{ url_for('history', policy_id=p.policy_id) }}">see the policy</a>.</p>
"""


# Two things about this guard, both learned the hard way.
#
# It belongs at the very END of the file. `gemdb app.py` executes top to
# bottom, so a guard next to serve() would start the server before the
# templates below exist and every route would raise NameError -- which
# importing the module hides completely, because an import finishes the file
# before any route runs.
#
# And the entry point is `serve`, not `main`, because under Grail `__main__`
# is one namespace shared by every script the database has ever run, and
# dispatch is by argument count with defaults not counting. `main()` here
# reached another script's zero-argument `main` and failed inside it.
if __name__ == "__main__":
    serve()
