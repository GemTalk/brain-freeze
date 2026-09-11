"""Every page and payload the app renders, as module constants.

Inline strings, not files: `render_template_string` is exercised in Grail's
own suite and file-based `render_template` is not. That constraint is why
these are here at all, and it says nothing about which FILE they live in --
so they live beside the routes that render them rather than swamping them.
`app.py` was 1,025 lines, 280 of them this.

A top-level module on purpose. Grail keeps a committed PACKAGE module compiled
in the database and serves that copy forever after; a top-level module is
recompiled from disk each run. Measured, because it decides whether editing a
template needs a `redeploy.py`. It does not.

Money never reaches a template raw -- see `render()` in app.py, which puts
`usd` in every context.
"""

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
    <td class="num">{{ usd(p.total_paid) }}</td>
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
    <label class="opt"><input type="radio" name="migraine_history" value="no" checked> No</label>
    <label class="opt"><input type="radio" name="migraine_history" value="yes"> Yes</label></fieldset>
  <fieldset><legend>Diagnosed with tension headaches?</legend>
    <label class="opt"><input type="radio" name="tension_type_headache_history" value="no" checked> No</label>
    <label class="opt"><input type="radio" name="tension_type_headache_history" value="yes"> Yes</label></fieldset>
  <fieldset><legend>How fast do they usually eat something cold?</legend>
    {% for label, value in speeds %}
    <label class="opt"><input type="radio" name="typical_consumption_speed" value="{{ value }}"
      {% if value == 'moderate' %}checked{% endif %}> {{ label }}</label>
    {% endfor %}</fieldset>
  <fieldset><legend>Favourite cold treat</legend>
    {% for t in triggers %}
    <label class="opt"><input type="radio" name="favourite_trigger" value="{{ t }}"
      {% if loop.first %}checked{% endif %}> {{ t }}</label>
    {% endfor %}</fieldset>
  <button type="submit">See the price</button>
</form>
"""

# The five answers used to be posted back through this screen as hidden
# fields, because a quote had nowhere to live. It has one now, so the only
# thing this form carries is which plan was picked -- and that rides on the
# button rather than on a hidden input, which is what a button's `value` is
# for. There is no hidden field anywhere in this file, and
# tests/test_quote_flow.py pins that.
PLANS = _STYLE + """
<h1>Three ways to cover it</h1>
<p class="sub">Risk band <strong>{{ q.risk_tier }}</strong>,
   scored <span class="num">{{ q.score }}</span>.</p>
<p class="muted"><span class="num">{{ q.quote_id }}</span>,
   quoted {{ q.quoted_on }}. This quote is saved &mdash; come back to it at
   <a href="{{ url_for('saved_quote', quote_id=q.quote_id) }}"
      class="num">/quote/{{ q.quote_id }}</a>.</p>

{% if q.policy_id %}
<div class="warn">This quote was taken up as
  <a href="{{ url_for('history', policy_id=q.policy_id) }}"
     class="num">{{ q.policy_id }}</a>.</div>
{% endif %}

<div class="card">
  <strong>How that score was reached</strong>
  <table>
    {% for label, points in q.breakdown %}
    <tr><td>{{ label }}</td>
        <td class="num" style="text-align:right">{{ '%+.1f'|format(points) }}</td></tr>
    {% endfor %}
  </table>
</div>

{% for name, plan in q.plans.items() %}
<form method="post"
      action="{{ url_for('accept_quote', quote_id=q.quote_id) }}" class="card">
  <div class="row">
    <div>
      <strong>{{ name }}</strong>
      <div class="muted">{{ usd(plan.limit) }} an episode,
        {{ usd(plan.deductible) }} deductible</div>
    </div>
    <div style="text-align:right">
      <div class="big num">{{ usd(plan.annual) }}</div>
      <div class="muted">a year &middot; {{ usd(plan.monthly) }} a month</div>
    </div>
  </div>
  <button type="submit" name="plan" value="{{ name }}">Take out {{ name }}</button>
</form>
{% endfor %}
"""

HISTORY = _STYLE + """
<h1 class="num">{{ p.policy_id }}</h1>
<p class="sub">{{ p.plan_name }} &middot; {{ p.risk_tier }} band,
  <span class="num">{{ p.underwriting_risk_score }}</span> &middot;
  {{ usd(p.annual_premium) }} a year &middot;
  {{ usd(p.coverage_limit) }} an episode,
  {{ usd(p.deductible) }} deductible &middot;
  <span class="tag {{ cover_css }}">{{ cover }}</span>
</p>

<div class="card row">
  <div><div class="big num">{{ p.events|length }}</div><div class="muted">cold treats</div></div>
  <div><div class="big num">{{ p.brain_freeze_events|length }}</div><div class="muted">gave a headache</div></div>
  <div><div class="big num">{{ p.claims|length }}</div><div class="muted">claims sent</div></div>
  <div><div class="big num">{{ usd(p.total_paid) }}</div><div class="muted">paid out</div></div>
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
            <span class="num">{{ usd(e.claim.approved) }}</span>
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
<h1>{{ usd(c.approved) }} is yours</h1>
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
        <td class="num" style="text-align:right">{{ usd(c.requested) }}</td></tr>
    {% if c.is_approved %}
    <tr><td>Trimmed to your {{ usd(p.coverage_limit) }} episode cap</td>
        <td class="num" style="text-align:right">&minus;{{ usd(trimmed) }}</td></tr>
    <tr><td>Your deductible</td>
        <td class="num" style="text-align:right">&minus;{{ usd(p.deductible) }}</td></tr>
    {% else %}
    <tr><td colspan="2"><span class="tag no">{{ c.reason }}</span></td></tr>
    {% endif %}
    <tr><td><strong>Paid to you</strong></td>
        <td class="num" style="text-align:right">
          <strong>{{ usd(c.approved) }}</strong></td></tr>
  </table>
</div>

<p class="muted">It goes on the record either way &mdash;
  <a href="{{ url_for('history', policy_id=p.policy_id) }}">see the policy</a>.</p>
"""
