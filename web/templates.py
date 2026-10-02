"""Every page the app renders, as module constants.

Inline strings, not files: `render_template_string` is exercised in Grail's
own suite and file-based `render_template` is not. That also rules out
`{% extends %}` and `{% import %}`, which need a loader, so a page is built
here in Python: `page()` glues the shared head and foot around a body, and
icons are written into each page's string when this module loads.

An edit to a template is live in a running app once it is loaded with
`gemdb tools/load.py`. See routes.py.

Money never reaches a template raw -- `pages.render()` puts `usd` in every
context, and `css` (the stylesheet below) with it.

THE ID CARD IS ONE SVG

`ID_CARD` is the whole design of the card: the page shows it inline, the
"Download image" button draws that same SVG onto a canvas, and
`/policies/<id>/card.svg` serves it on its own. To use a different design,
replace that one string with any SVG that reads the fields `pages.id_card()`
provides. Keep its fonts to the system stacks used below: a web font does
not load inside an SVG drawn to a canvas, and the PNG would not match.
"""

import re

STYLE = """
:root {
  --bg: #f3f7fb; --surface: #ffffff; --ink: #12223a; --ink-2: #3a4c64;
  --muted: #66778c; --line: #dbe4ee; --line-2: #ebf0f6;
  --ice: #2a8bd8; --ice-deep: #1b6aac; --ice-soft: #e2f0fb; --ice-wash: #f2f8fd;
  --mint: #18885f; --mint-soft: #dcf4ea; --berry: #b8325a; --berry-soft: #fce8ee;
  --amber: #a86a12; --amber-soft: #fff4dc;
  --radius: 18px; --radius-sm: 11px;
  --shadow: 0 1px 2px rgba(18,34,58,.05), 0 8px 24px rgba(18,34,58,.06);
  --font: "Plus Jakarta Sans", ui-sans-serif, system-ui, -apple-system,
          "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; font-family: var(--font); color: var(--ink);
       background: var(--bg); line-height: 1.55; font-size: 16px;
       min-height: 100vh; display: flex; flex-direction: column; }
a { color: var(--ice-deep); text-underline-offset: 3px; }
a:hover { color: var(--ice); }
h1, h2, h3 { line-height: 1.15; letter-spacing: -.02em; margin: 0 0 .4rem; }
h1 { font-size: clamp(1.9rem, 4.2vw, 2.7rem); font-weight: 800; }
h2 { font-size: 1.35rem; font-weight: 800; }
h3 { font-size: 1.05rem; font-weight: 700; }
p { margin: 0 0 .8rem; }
.wrap { max-width: 68rem; margin: 0 auto; padding: 0 1.25rem; }
.narrow { max-width: 46rem; }
main { padding: 2.2rem 0 3.5rem; flex: 1; }
.section { margin-top: 2.6rem; }
.eyebrow { font-size: .76rem; font-weight: 800; letter-spacing: .1em;
           text-transform: uppercase; color: var(--ice-deep); margin: 0 0 .5rem; }
.sub { color: var(--ink-2); font-size: 1.05rem; margin: .2rem 0 1rem; }
.muted { color: var(--muted); font-size: .86rem; }
.num { font-variant-numeric: tabular-nums; }
.id { font-family: var(--mono); font-size: .92em; letter-spacing: -.01em;
       white-space: nowrap; }
h1.id { font-size: clamp(1.9rem, 4.2vw, 2.7rem); letter-spacing: -.03em; }
.big { font-size: 1.75rem; font-weight: 800; letter-spacing: -.02em;
       line-height: 1.1; }

/* header and footer */
.top { background: rgba(255,255,255,.88); border-bottom: 1px solid var(--line);
       position: sticky; top: 0; z-index: 10; backdrop-filter: blur(8px); }
.top .wrap { display: flex; align-items: center; gap: 1rem; min-height: 4rem;
             flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: .6rem; color: var(--ink);
         text-decoration: none; font-weight: 800; font-size: 1.1rem;
         letter-spacing: -.02em; margin-right: auto; }
.brand:hover { color: var(--ink); }
.mark { display: inline-flex; width: 2.1rem; height: 2.1rem; border-radius: 10px;
        align-items: center; justify-content: center; color: #fff;
        background: linear-gradient(135deg, var(--ice), var(--ice-deep));
        box-shadow: 0 2px 0 var(--ice-deep); }
.brand small { display: block; font-size: .68rem; font-weight: 700;
               letter-spacing: .12em; text-transform: uppercase;
               color: var(--muted); }
.nav { display: flex; gap: .3rem; flex-wrap: wrap; }
.nav a { color: var(--ink-2); text-decoration: none; font-weight: 600;
         font-size: .93rem; padding: .45rem .8rem; border-radius: 999px; }
.nav a:hover { background: var(--ice-wash); color: var(--ink); }
.nav a.on { background: var(--ice-soft); color: var(--ice-deep); }
.foot { border-top: 1px solid var(--line); padding: 1.6rem 0 2.4rem;
        color: var(--muted); font-size: .85rem; }
.foot p { max-width: 44rem; margin: 0; }

/* buttons */
button, .btn { font: inherit; font-weight: 700; font-size: .97rem;
  display: inline-flex; align-items: center; gap: .45rem;
  padding: .72rem 1.25rem; border-radius: 999px; border: 1.5px solid transparent;
  background: var(--ice); color: #fff; cursor: pointer; text-decoration: none;
  box-shadow: 0 3px 0 var(--ice-deep);
  transition: transform .15s ease, box-shadow .15s ease, background .15s ease; }
button:hover, .btn:hover { color: #fff; background: #3497e4;
  transform: translateY(-1px); box-shadow: 0 4px 0 var(--ice-deep); }
button:active, .btn:active { transform: translateY(1px);
  box-shadow: 0 1px 0 var(--ice-deep); }
.btn.ghost { background: var(--surface); color: var(--ink); border-color: var(--line);
             box-shadow: 0 2px 0 var(--line); }
.btn.ghost:hover { color: var(--ink); background: var(--ice-wash); }
.btn.lg { padding: .9rem 1.5rem; font-size: 1.05rem; }
.actions { display: flex; flex-wrap: wrap; gap: .7rem; align-items: center;
           margin: 1.2rem 0; }

/* cards, tags, notes */
.card { background: var(--surface); border: 1px solid var(--line);
        border-radius: var(--radius); padding: 1.3rem 1.45rem; margin: 1rem 0;
        box-shadow: var(--shadow); }
.row { display: flex; justify-content: space-between; gap: 1rem;
       align-items: baseline; flex-wrap: wrap; }
.card.row > div { flex: 1 1 7rem; }
.card.row > div .muted { margin-top: .2rem; }
.tag { display: inline-block; font-size: .78rem; font-weight: 700;
       padding: .18rem .62rem; border-radius: 999px; background: var(--line-2);
       color: var(--ink-2); white-space: nowrap; vertical-align: middle; }
.tag.ok { background: var(--mint-soft); color: var(--mint); }
.tag.no { background: var(--berry-soft); color: var(--berry); }
.tag.ice { background: var(--ice-soft); color: var(--ice-deep); }
.warn { background: var(--amber-soft); border: 1px solid #f2d9a6;
        color: #6d4a10; padding: .85rem 1.1rem; border-radius: var(--radius-sm);
        margin: .8rem 0; }
.note { background: var(--ice-wash); border: 1px solid var(--ice-soft);
        padding: .85rem 1.1rem; border-radius: var(--radius-sm); margin: .8rem 0; }

/* tables */
.table-wrap { overflow-x: auto; margin: 0 -.3rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .62rem .5rem; vertical-align: top;
         border-bottom: 1px solid var(--line-2); }
th { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase;
     color: var(--muted); font-weight: 700; }
tbody tr:hover td { background: var(--ice-wash); }
td.r, th.r { text-align: right; }
td.num { white-space: nowrap; }
td a { font-weight: 600; }

/* forms */
fieldset { border: 0; padding: 0; margin: 0 0 1.4rem; min-width: 0; }
legend, .q { font-weight: 700; padding: 0; margin-bottom: .55rem; }
.hint { color: var(--muted); font-size: .85rem; margin-top: .45rem; }
input[type=number], input[type=text], input[type=search] {
  font: inherit; color: var(--ink); background: #fff;
  border: 1.5px solid var(--line); border-radius: var(--radius-sm);
  padding: .62rem .85rem; min-width: 0; }
input[type=number] { width: 7rem; }
input:focus { outline: none; border-color: var(--ice);
              box-shadow: 0 0 0 4px var(--ice-soft); }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; }
.chip { position: relative; display: inline-block; }
.chip input { position: absolute; inset: 0; width: 100%; height: 100%;
              margin: 0; opacity: 0; cursor: pointer; z-index: 1; }
.chip span { display: inline-block; padding: .5rem .95rem; border-radius: 999px;
             border: 1.5px solid var(--line); background: #fff;
             font-weight: 600; font-size: .93rem; color: var(--ink-2);
             transition: background .12s ease, border-color .12s ease; }
.chip:hover span { border-color: #b9cde0; }
.chip input:checked + span { background: var(--ice-soft); border-color: var(--ice);
                             color: var(--ice-deep); }
.chip input:focus-visible + span { box-shadow: 0 0 0 4px var(--ice-soft); }
.search { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; }
.search input { flex: 1 1 12rem; }
.search button { box-shadow: none; padding: .62rem 1.1rem; }
.search button:hover { box-shadow: none; transform: none; }

/* the quote wizard */
.steps { display: flex; gap: .5rem; list-style: none; padding: 0;
         margin: 0 0 1.4rem; flex-wrap: wrap; }
.steps li { display: flex; align-items: center; gap: .5rem; font-weight: 700;
            font-size: .88rem; color: var(--muted); padding: .35rem .8rem .35rem .4rem;
            border-radius: 999px; background: var(--surface);
            border: 1px solid var(--line); }
.steps b { display: inline-flex; width: 1.6rem; height: 1.6rem; border-radius: 50%;
           align-items: center; justify-content: center; font-size: .8rem;
           background: var(--line-2); color: var(--ink-2); }
.steps .now { color: var(--ice-deep); border-color: var(--ice); }
.steps .now b { background: var(--ice); color: #fff; }
.steps .done b { background: var(--mint-soft); color: var(--mint); }
.qgrid { display: grid; gap: .2rem 2rem;
         grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); }

/* plans */
.plans { display: grid; gap: 1rem; margin: 1rem 0;
         grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); }
.plans .card { margin: 0; display: flex; flex-direction: column; gap: .3rem;
               position: relative; }
.plans .card.pick { border: 2px solid var(--ice); }
.plans .card.chosen { border: 2px solid var(--mint); }
.plans .badge { position: absolute; top: -.75rem; right: 1rem; }
.plans ul { list-style: none; padding: 0; margin: .6rem 0 1rem; flex: 1; }
.plans li { padding: .32rem 0; border-top: 1px dashed var(--line);
            font-size: .93rem; color: var(--ink-2); }
.plans li:first-child { border-top: 0; }
.plans button { justify-content: center; }
.price { display: flex; align-items: baseline; gap: .4rem; flex-wrap: wrap; }

/* the home page */
.hero { position: relative; overflow: hidden; border-radius: 26px;
        padding: clamp(1.6rem, 5vw, 3.2rem); border: 1px solid var(--line);
        background:
          radial-gradient(circle at 88% 12%, #d4e9fa 0, transparent 38%),
          radial-gradient(circle at 70% 110%, #e6f3fc 0, transparent 40%),
          linear-gradient(180deg, #ffffff, var(--ice-wash)); }
.hero h1 { max-width: 15ch; font-size: clamp(2.2rem, 5.4vw, 3.5rem); }
.hero .sub { max-width: 36rem; }
.hero .flake { position: absolute; color: var(--ice); opacity: .14;
               pointer-events: none; }
.how { display: grid; gap: 1rem; margin: 1rem 0;
       grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); }
.how > div { display: flex; gap: .8rem; align-items: flex-start; }
.how b { flex: none; display: inline-flex; width: 2rem; height: 2rem;
         border-radius: 50%; align-items: center; justify-content: center;
         background: var(--ice-soft); color: var(--ice-deep); }
.how p { margin: .1rem 0 0; color: var(--muted); font-size: .9rem; }

/* the id card */
.idcard { max-width: 44rem; }
.idcard svg { display: block; width: 100%; height: auto; border-radius: 4%/6.3%;
              box-shadow: 0 2px 4px rgba(18,34,58,.08), 0 18px 40px rgba(18,34,58,.16); }

.pager { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
         margin-top: 1rem; }
.filters { display: flex; gap: .4rem; flex-wrap: wrap; margin: .2rem 0 .9rem; }
.filters a { text-decoration: none; }
.filters a.tag.on { background: var(--ink); color: #fff; }

@media (max-width: 640px) {
  .top .wrap { padding-top: .6rem; padding-bottom: .6rem; }
  .nav { width: 100%; }
  .nav a { padding: .35rem .65rem; }
  main { padding-top: 1.4rem; }
  .card { padding: 1.1rem 1.1rem; }
}
@media print {
  .top, .foot, .no-print { display: none !important; }
  body { background: #fff; }
  .idcard svg { box-shadow: none; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
"""

#: Shared by every page: the document head and the header. `@@TITLE@@` and
#: `@@NAV@@` are filled in by `page()` when the module loads, before Jinja
#: sees the string, so a title can itself use the context.
_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap">
<style>{{ css|safe }}</style>
</head>
<body>
{%- set nav = '@@NAV@@' %}
<header class="top">
  <div class="wrap">
    <a class="brand" href="{{ url_for('home') }}">
      <span class="mark">[[icon:snowflake:20]]</span>
      <span>Brain Freeze<small>Insurance</small></span>
    </a>
    <nav class="nav" aria-label="Main">
      <a href="{{ url_for('quote_form') }}" {% if nav == 'quote' %}class="on"{% endif %}>Get a quote</a>
      <a href="{{ url_for('policies') }}" {% if nav == 'policies' %}class="on"{% endif %}>Policies</a>
      <a href="{{ url_for('claims') }}" {% if nav == 'claims' %}class="on"{% endif %}>Claims</a>
    </nav>
  </div>
</header>
<main>
"""

_FOOT = """
</main>
<footer class="foot">
  <div class="wrap">
    <p>Brain Freeze is a demo, not real insurance. Every quote, policy and
    claim on these pages is a Python object stored in GemDB: the app reads and
    writes them directly, with no ORM and no SQL in between.</p>
  </div>
</footer>
</body>
</html>
"""


#: The icons, as the path data of a 24x24 stroked SVG.
_ICONS = {
    "snowflake": "M2 12h20M12 2v20m8-6-4-4 4-4M4 8l4 4-4 4m12-12-4 4-4-4m0 16 4-4 4 4",
    "arrow": "M5 12h14m-6-6 6 6-6 6",
    "back": "M19 12H5m6 6-6-6 6-6",
    "check": "m5 12 5 5L20 7",
    "download": "M12 3v12m-5-5 5 5 5-5M4 21h16",
    "print": "M6 9V3h12v6M6 18H4v-7h16v7h-2M8 14h8v7H8z",
    "card": "M3 5h18v14H3zM3 10h18M7 15h4",
}

#: `[[icon:arrow]]`, or `[[icon:snowflake:20]]` for a size other than 18.
_ICON_TAG = re.compile(r"\[\[icon:(\w+)(?::(\d+))?\]\]")


def _icon(found):
    size = found.group(2) or "18"
    return ('<svg width="%s" height="%s" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><path d="%s"/></svg>'
            % (size, size, _ICONS[found.group(1)]))


def page(title, nav, body):
    """A whole page: the shared head, `body`, the shared foot.

    `nav` names the header link to mark as the current one ('' for none).

    Icons are substituted here, in Python, rather than by a Jinja macro:
    defining a macro costs Grail about 0.4s on every render, which was most
    of the time each page took. Measured.
    """
    whole = (_HEAD.replace("@@TITLE@@", title).replace("@@NAV@@", nav)
             + body + _FOOT)
    return _ICON_TAG.sub(_icon, whole)


#: "Showing 1-25 of 900." with previous and next links, for any paged list.
#: Expects a `pager` from `pages.pager()` in the context.
_PAGER = """
<div class="pager muted">
  {% if pager.previous is not none %}
  <a href="{{ pager.previous }}">&larr; previous</a>
  {% endif %}
  <span>Showing {{ pager.first }}&ndash;{{ pager.last }} of {{ pager.total }}.</span>
  {% if pager.next is not none %}
  <a href="{{ pager.next }}">next &rarr;</a>
  {% endif %}
</div>
"""


HOME = page("Brain Freeze Insurance", "", """
<div class="wrap">
  <section class="hero">
    <span class="flake" style="right:-2.5rem; top:-2.5rem">[[icon:snowflake:260]]</span>
    <span class="flake" style="right:11rem; bottom:-2rem">[[icon:snowflake:110]]</span>
    <p class="eyebrow">Make-believe insurance, real database</p>
    <h1>Cover for the coldest moments.</h1>
    <p class="sub">Brain Freeze insures kids against ice-cream headaches. The
      insurance is pretend; the software isn&rsquo;t. Every quote, policy and
      claim here is a plain Python object living in GemDB, priced and judged
      by the same rules the notebook and the agent use.</p>
    <p class="muted">Right now the book holds {{ stats.policies }} policyholders
      and {{ stats.claims }} claims.</p>
    <div class="actions">
      <a class="btn lg" href="{{ url_for('quote_form') }}">Start a quote [[icon:arrow]]</a>
      <a class="btn ghost" href="{{ url_for('claims') }}">Browse claims</a>
    </div>
  </section>

  <section class="section">
    <div class="how">
      <div><b>1</b><div><h3>Answer five questions</h3>
        <p>Age, eating speed, favourite treat and two health questions.</p></div></div>
      <div><b>2</b><div><h3>Pick from three prices</h3>
        <p>See exactly how your risk score was worked out.</p></div></div>
      <div><b>3</b><div><h3>Get your ID card</h3>
        <p>Your policy is saved straight away. Download the card or print it.</p></div></div>
    </div>
  </section>

  <section class="section">
    <h2>The plans</h2>
    <p class="muted">What you pay depends on your answers; these are the
      lowest prices each plan comes to.</p>
    <div class="plans">
      {% for plan in plans %}
      <div class="card{% if plan.popular %} pick{% endif %}">
        {% if plan.popular %}<span class="tag ice badge">Most chosen</span>{% endif %}
        <h3>{{ plan.name }}</h3>
        <div class="price"><span class="big num">{{ usd(plan.from_annual) }}</span>
          <span class="muted">a year, at the lowest</span></div>
        <ul>
          <li><strong class="num">{{ usd(plan.limit) }}</strong> paid per episode</li>
          <li><strong class="num">{{ usd(plan.deductible) }}</strong> deductible</li>
          <li>Up to {{ claim_limit }} approved claims a year</li>
          <li class="muted">{{ plan.holders }} policyholders on this plan</li>
        </ul>
      </div>
      {% endfor %}
    </div>
    <div class="actions">
      <a class="btn lg" href="{{ url_for('quote_form') }}">Start a quote [[icon:arrow]]</a>
      <span class="muted">Takes about a minute. Nothing to sign up for.</span>
    </div>
  </section>
</div>
""")


_STEPS = """
<ol class="steps" aria-label="Quote progress">
  <li class="{{ 'now' if step == 1 else 'done' }}"><b>{% if step > 1 %}[[icon:check:14]]{% else %}1{% endif %}</b> About the member</li>
  <li class="{{ 'now' if step == 2 else '' }}"><b>2</b> Choose a plan</li>
  <li><b>[[icon:card:14]]</b> ID card</li>
</ol>
"""

QUOTE_FORM = page("Get a quote &middot; Brain Freeze", "quote", """
<div class="wrap narrow">
  {% set step = 1 %}""" + _STEPS + """
  <h1>Tell us about the member</h1>
  <p class="sub">Five questions. We work the price out from the answers.</p>
  <form method="post" action="{{ url_for('quote_result') }}" class="card">
    <div class="qgrid">
      <fieldset><legend>How old are they?</legend>
        <input type="number" name="age" value="{{ a.age }}" min="5" max="19" required>
        <div class="hint">Cover is for ages 5 to 19.</div></fieldset>
      <fieldset><legend>Diagnosed with migraine?</legend>
        <div class="chips">
          <label class="chip"><input type="radio" name="migraine_history" value="no" {% if not a.migraine_history %}checked{% endif %}><span>No</span></label>
          <label class="chip"><input type="radio" name="migraine_history" value="yes" {% if a.migraine_history %}checked{% endif %}><span>Yes</span></label>
        </div></fieldset>
      <fieldset><legend>Diagnosed with tension headaches?</legend>
        <div class="chips">
          <label class="chip"><input type="radio" name="tension_type_headache_history" value="no" {% if not a.tension_type_headache_history %}checked{% endif %}><span>No</span></label>
          <label class="chip"><input type="radio" name="tension_type_headache_history" value="yes" {% if a.tension_type_headache_history %}checked{% endif %}><span>Yes</span></label>
        </div></fieldset>
    </div>
    <fieldset><legend>How fast do they usually eat something cold?</legend>
      <div class="chips">
      {% for label, value in speeds %}
        <label class="chip"><input type="radio" name="typical_consumption_speed" value="{{ value }}" {% if value == a.typical_consumption_speed %}checked{% endif %}><span>{{ label }}</span></label>
      {% endfor %}
      </div></fieldset>
    <fieldset><legend>Favourite cold treat</legend>
      <div class="chips">
      {% for t in triggers %}
        <label class="chip"><input type="radio" name="favourite_trigger" value="{{ t }}" {% if t == a.favourite_trigger %}checked{% endif %}><span>{{ t|capitalize }}</span></label>
      {% endfor %}
      </div></fieldset>
    <div class="row" style="align-items:center">
      <span class="muted">Your quote is saved, so you can come back to it.</span>
      <button type="submit">See my prices [[icon:arrow]]</button>
    </div>
  </form>
</div>
""")

# Which plan was picked rides on the button that picks it, not on a hidden
# input -- what a button's `value` is for. There is no hidden field on any
# page, and tests/test_app.py pins that for this one.
PLANS = page("Your quote {{ q.quote_id }} &middot; Brain Freeze", "quote", """
<div class="wrap">
  {% set step = 2 %}""" + _STEPS + """
  <h1>Choose a plan</h1>
  <p class="sub">Risk band <strong>{{ q.risk_tier }}</strong>, scored
     <span class="num">{{ q.score }}</span> out of 100.</p>
  <p class="muted">Quote <span class="id">{{ q.quote_id }}</span>, given
     {{ q.quoted_on }}, is saved at
     <a href="{{ url_for('saved_quote', quote_id=q.quote_id) }}" class="id">/quote/{{ q.quote_id }}</a>.
     <a href="{{ url_for('quote_form', answers=q.quote_id) }}">Change the answers</a></p>

  {% if q.policy_id %}
  <div class="note">This quote was taken up as policy
    <a href="{{ url_for('history', policy_id=q.policy_id) }}" class="id">{{ q.policy_id }}</a>.
    <a href="{{ url_for('id_card', policy_id=q.policy_id) }}">See its ID card</a></div>
  {% endif %}

  <div class="plans">
  {% for name, plan in q.plans.items() %}
    {% if q.policy_id %}
    <div class="card{% if name == chosen %} chosen{% endif %}">
      {% if name == chosen %}<span class="tag ok badge">Chosen</span>{% endif %}
    {% else %}
    <form method="post" action="{{ url_for('accept_quote', quote_id=q.quote_id) }}"
          class="card{% if name == popular %} pick{% endif %}">
      {% if name == popular %}<span class="tag ice badge">Most chosen</span>{% endif %}
    {% endif %}
      <h3>{{ name }}</h3>
      <div class="price"><span class="big num">{{ usd(plan.annual) }}</span>
        <span class="muted">a year &middot; {{ usd(plan.monthly) }} a month</span></div>
      <ul>
        <li><strong class="num">{{ usd(plan.limit) }}</strong> paid per episode</li>
        <li><strong class="num">{{ usd(plan.deductible) }}</strong> deductible</li>
        <li>Up to {{ claim_limit }} approved claims a year</li>
      </ul>
    {% if q.policy_id %}
    </div>
    {% else %}
      <button type="submit" name="plan" value="{{ name }}">Choose {{ name }}</button>
    </form>
    {% endif %}
  {% endfor %}
  </div>

  <details class="card">
    <summary><strong>How we worked out the score</strong></summary>
    <div class="table-wrap"><table>
      {% for label, points in q.breakdown %}
      <tr><td>{{ label }}</td>
          <td class="num r">{{ '%+.1f'|format(points) }}</td></tr>
      {% endfor %}
      <tr><td><strong>Score</strong></td>
          <td class="num r"><strong>{{ q.score }}</strong></td></tr>
    </table></div>
    <p class="muted">Below {{ bands.low }} is Low, below {{ bands.medium }} is
      Medium, anything higher is High. The band sets the price.</p>
  </details>
</div>
""")

ID_CARD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 856 540"
  width="856" height="540" role="img"
  aria-label="Brain Freeze ID card for policy {{ card.policy_id }}">
<defs>
  <linearGradient id="bf-sky" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#2f95e0"/><stop offset="1" stop-color="#174f88"/>
  </linearGradient>
  <clipPath id="bf-edge"><rect width="856" height="540" rx="34"/></clipPath>
</defs>
<g clip-path="url(#bf-edge)"
   font-family="ui-sans-serif, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif">
  <rect width="856" height="540" fill="url(#bf-sky)"/>
  <circle cx="770" cy="30" r="200" fill="#fff" fill-opacity=".07"/>
  <circle cx="650" cy="250" r="90" fill="#fff" fill-opacity=".05"/>
  <g transform="translate(600 -40) scale(11)" stroke="#fff" stroke-opacity=".10"
     stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M2 12h20M12 2v20m8-6-4-4 4-4M4 8l4 4-4 4m12-12-4 4-4-4m0 16 4-4 4 4"/>
  </g>
  <rect x="52" y="48" width="56" height="56" rx="15" fill="#fff" fill-opacity=".16"/>
  <g transform="translate(64 60) scale(1.33)" stroke="#fff" stroke-width="2.2"
     stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M2 12h20M12 2v20m8-6-4-4 4-4M4 8l4 4-4 4m12-12-4 4-4-4m0 16 4-4 4 4"/>
  </g>
  <text x="126" y="76" fill="#fff" font-size="27" font-weight="800">Brain Freeze</text>
  <text x="127" y="99" fill="#cfe5f8" font-size="13" font-weight="700"
        letter-spacing="2.6">INSURANCE &#183; MEMBER ID CARD</text>
  <rect x="628" y="54" width="176" height="44" rx="22" fill="#fff"/>
  <text x="716" y="83" text-anchor="middle" fill="#174f88" font-size="19"
        font-weight="800">{{ card.plan }} plan</text>

  <text x="56" y="178" fill="#cfe5f8" font-size="13" font-weight="700"
        letter-spacing="2.4">POLICY NUMBER</text>
  <text x="54" y="236" fill="#fff" font-size="58" font-weight="700" letter-spacing="1"
        font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{{ card.policy_id }}</text>
  <text x="56" y="278" fill="#e4f1fc" font-size="19" font-weight="600">{{ card.member }}</text>

  <rect y="318" width="856" height="222" fill="#fff"/>
  <g font-size="12" font-weight="700" letter-spacing="2" fill="#66778c">
    <text x="56" y="362">COVER PER EPISODE</text>
    <text x="268" y="362">DEDUCTIBLE</text>
    <text x="440" y="362">PREMIUM</text>
    <text x="640" y="362">RISK BAND</text>
    <text x="56" y="438">VALID</text>
    <text x="440" y="438">CLAIMS A YEAR</text>
    <text x="640" y="438">STATUS</text>
  </g>
  <g font-size="25" font-weight="800" fill="#12223a">
    <text x="56" y="394">{{ card.cover }}</text>
    <text x="268" y="394">{{ card.deductible }}</text>
    <text x="440" y="394">{{ card.premium }}<tspan font-size="15" font-weight="600" fill="#66778c"> /yr</tspan></text>
    <text x="640" y="394">{{ card.risk_tier }}</text>
    <text x="56" y="470" font-size="21">{{ card.valid_from }} &#8211; {{ card.valid_to }}</text>
    <text x="440" y="470" font-size="21">Up to {{ card.claims_a_year }}</text>
    <text x="640" y="470" font-size="21">{{ card.status }}</text>
  </g>
  <text x="56" y="514" fill="#8a99ab" font-size="13" font-weight="600">Stored in GemDB &#183; a demo, not real insurance</text>
  <text x="800" y="514" text-anchor="end" fill="#8a99ab" font-size="13"
        font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">brain-freeze</text>
</g>
</svg>"""

CARD_PAGE = page("ID card {{ card.policy_id }} &middot; Brain Freeze", "", """
<div class="wrap">
  <p class="eyebrow">You&rsquo;re covered</p>
  <h1>Your ID card</h1>
  <p class="sub">{{ p.plan_name }} plan, <span class="num">{{ usd(p.annual_premium) }} a year</span>
    &middot; {{ usd(p.coverage_limit) }} an episode, {{ usd(p.deductible) }} deductible.</p>
  <div class="idcard" id="id-card">""" + ID_CARD + """</div>
  <div class="actions no-print">
    <button type="button" id="save-png" data-filename="{{ card.policy_id }}-id-card.png">
      [[icon:download]] Download image</button>
    <a class="btn ghost" href="{{ url_for('id_card_svg', policy_id=p.policy_id) }}"
       download="{{ card.policy_id }}-id-card.svg">Download SVG</a>
    <button type="button" class="btn ghost" onclick="window.print()">[[icon:print]] Print</button>
  </div>
  <div class="actions no-print">
    <a href="{{ url_for('history', policy_id=p.policy_id) }}">See the policy</a>
    <a href="{{ url_for('claim_form', policy_id=p.policy_id) }}">File a claim</a>
  </div>
</div>
<script>
// Draw the card's own SVG onto a canvas and save that, so the image is
// always the card on the page and never a second copy of its design.
document.getElementById('save-png').addEventListener('click', function () {
  var button = this;
  var svg = document.querySelector('#id-card svg');
  var box = svg.viewBox.baseVal, scale = 2;
  var image = new Image();
  image.onload = function () {
    var canvas = document.createElement('canvas');
    canvas.width = box.width * scale;
    canvas.height = box.height * scale;
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(function (blob) {
      var link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = button.dataset.filename;
      link.click();
      setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    }, 'image/png');
  };
  image.src = 'data:image/svg+xml;charset=utf-8,' +
    encodeURIComponent(new XMLSerializer().serializeToString(svg));
});
</script>
""")

POLICIES = page("Policies &middot; Brain Freeze", "policies", """
<div class="wrap">
  <h1>Policyholders</h1>
  <p class="sub">{{ total }} policyholders, live in the database.</p>
  <form method="get" action="{{ url_for('policies') }}" class="card search">
    <label for="policy" class="q" style="margin:0">Go to a policy</label>
    <input type="text" id="policy" name="policy" value="{{ wanted }}"
           placeholder="BF-100539" autocomplete="off">
    <button type="submit">Find</button>
    {% if wanted %}<a href="{{ url_for('policies') }}">clear</a>{% endif %}
  </form>
  <div class="card">
  {% if rows %}
  <div class="table-wrap"><table>
    <thead><tr><th>Policy</th><th>Plan</th><th>Band</th><th>Cover</th>
        <th class="r">Claims</th><th class="r">Paid</th></tr></thead>
    <tbody>
    {% for p, label, css in rows %}
    <tr>
      <td><a href="{{ url_for('history', policy_id=p.policy_id) }}"
             class="id">{{ p.policy_id }}</a></td>
      <td>{{ p.plan_name }}</td>
      <td class="num">{{ p.risk_tier }}, {{ p.underwriting_risk_score }}</td>
      <td><span class="tag {{ css }}">{{ label }}</span></td>
      <td class="num r">{{ p.approved_claims|length }}/{{ p.claims|length }}</td>
      <td class="num r">{{ usd(p.total_paid) }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% endif %}
  {% if not wanted %}""" + _PAGER + """
  {% elif not rows %}
  <p class="muted">Nothing matches &ldquo;{{ wanted }}&rdquo;.</p>
  {% endif %}
  </div>
</div>
""")

HISTORY = page("{{ p.policy_id }} &middot; Brain Freeze", "policies", """
<div class="wrap">
  <p class="eyebrow">Policy</p>
  <h1 class="id">{{ p.policy_id }}</h1>
  <p class="sub">{{ p.plan_name }} &middot; {{ p.risk_tier }} band,
    <span class="num">{{ p.underwriting_risk_score }}</span> &middot;
    {{ usd(p.annual_premium) }} a year &middot;
    {{ usd(p.coverage_limit) }} an episode,
    {{ usd(p.deductible) }} deductible &middot;
    <span class="tag {{ cover_css }}">{{ cover }}</span>
  </p>
  <div class="actions">
    <a class="btn" href="{{ url_for('claim_form', policy_id=p.policy_id) }}">File a claim</a>
    <a class="btn ghost" href="{{ url_for('id_card', policy_id=p.policy_id) }}">[[icon:card]] ID card</a>
  </div>

  <div class="card row">
    <div><div class="big num">{{ p.events|length }}</div><div class="muted">cold treats</div></div>
    <div><div class="big num">{{ p.brain_freeze_events|length }}</div><div class="muted">gave a headache</div></div>
    <div><div class="big num">{{ p.claims|length }}</div><div class="muted">claims sent</div></div>
    <div><div class="big num">{{ usd(p.total_paid) }}</div><div class="muted">paid out</div></div>
    <div><div class="big num">{{ p.approved_claims|length }}/{{ limit }}</div><div class="muted">claims used</div></div>
  </div>

  <div class="card">
    <h2>Every cold treat on record</h2>
    {% if not p.events %}
    <p class="muted">Nothing yet. When something cold causes trouble, file it
       and it will appear here.</p>
    {% else %}
    <div class="table-wrap"><table>
      <thead><tr><th>Date</th><th>Treat</th><th>Claim</th><th>Outcome</th></tr></thead>
      <tbody>
      {% for e in p.events %}
      <tr>
        <td class="num">{{ e.event_date }}</td>
        <td>{{ e.trigger }}{% if not e.brain_freeze %}
            <span class="muted">&middot; no headache</span>{% endif %}</td>
        <td>{% if e.claim %}<a class="id" href="{{ url_for('decision', policy_id=p.policy_id, claim_id=e.claim.claim_id) }}">{{ e.claim.claim_id }}</a>{% endif %}</td>
        <td>{% if not e.claim %}<span class="muted">not claimed</span>
            {% elif e.claim.is_approved %}
              <span class="tag ok num">{{ usd(e.claim.approved) }}</span>
            {% else %}<span class="tag no">{{ e.claim.reason }}</span>{% endif %}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table></div>
    {% endif %}
  </div>
  <p class="muted">The treats that caused no headache are here too. They are
    the denominator &mdash; without them, how often a slushie causes brain
    freeze is not a question the data can answer.</p>
</div>
""")

CLAIM_FORM = page("File a claim on {{ p.policy_id }} &middot; Brain Freeze", "claims", """
<div class="wrap narrow">
  <p class="eyebrow">Claim on <a class="id" href="{{ url_for('history', policy_id=p.policy_id) }}">{{ p.policy_id }}</a></p>
  <h1>What happened?</h1>
  <p class="sub">Tell us about the episode. We work the money out from your
    answers &mdash; there is no figure to type in.</p>

  {% for note in warnings %}<div class="warn">{{ note }}</div>{% endfor %}

  <form method="post" action="{{ url_for('file_claim', policy_id=p.policy_id) }}"
        class="card">
    <fieldset><legend>What did they have?</legend>
      <div class="chips">{% for t in triggers %}
      <label class="chip"><input type="radio" name="trigger" value="{{ t }}"
        {% if loop.first %}checked{% endif %}><span>{{ t|capitalize }}</span></label>{% endfor %}
      </div></fieldset>
    <fieldset><legend>How cold was it?</legend>
      <div class="chips">{% for label, value in colds %}
      <label class="chip"><input type="radio" name="cold" value="{{ label }}"
        {% if loop.first %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}
      </div>
      <div class="hint">A band, not a reading &mdash; nobody owns a
        thermometer for this.</div></fieldset>
    <fieldset><legend>How much of it?</legend>
      <div class="chips">{% for label, value in portions %}
      <label class="chip"><input type="radio" name="portion" value="{{ label }}"
        {% if loop.index0 == 2 %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}
      </div></fieldset>
    <fieldset><legend>How fast?</legend>
      <div class="chips">{% for label, value in speeds %}
      <label class="chip"><input type="radio" name="speed" value="{{ label }}"
        {% if loop.index0 == 1 %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}
      </div></fieldset>
    <div class="qgrid">
      <fieldset><legend>How bad was it?</legend>
        <input type="number" name="pain" value="5" min="0" max="10">
        <div class="hint">0 is barely noticed, 10 is the worst ever.</div></fieldset>
      <fieldset><legend>Where did it hurt?</legend>
        <div class="chips">{% for l in locations %}
        <label class="chip"><input type="radio" name="location" value="{{ l }}"
          {% if loop.first %}checked{% endif %}><span>{{ l }}</span></label>{% endfor %}
        </div></fieldset>
    </div>
    <fieldset><legend>How long did it last?</legend>
      <div class="chips">{% for label, value in durations %}
      <label class="chip"><input type="radio" name="duration" value="{{ label }}"
        {% if loop.index0 == 2 %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}
      </div></fieldset>
    <fieldset><legend>What did it feel like?</legend>
      <div class="chips">{% for q in qualities %}
      <label class="chip"><input type="radio" name="quality" value="{{ q }}"
        {% if loop.first %}checked{% endif %}><span>{{ q }}</span></label>{% endfor %}
      </div></fieldset>
    <div class="row" style="align-items:center">
      <span class="muted">{{ p.plan_name }}: {{ usd(p.coverage_limit) }} an episode,
        {{ usd(p.deductible) }} deductible.</span>
      <button type="submit">Send the claim [[icon:arrow]]</button>
    </div>
  </form>
</div>
""")

DECISION = page("Claim {{ c.claim_id }} &middot; Brain Freeze", "claims", """
<div class="wrap narrow">
  <p class="eyebrow">{% if c.is_approved %}Approved{% else %}Refused{% endif %}</p>
  {% if c.is_approved %}
  <h1>{{ usd(c.approved) }} is yours</h1>
  {% else %}
  <h1>Not this time</h1>
  {% endif %}
  <p class="sub num">{{ c.claim_id }} &middot; {{ e.trigger }}
    &middot; {{ e.event_date }}</p>

  <div class="card">
    <div class="table-wrap"><table>
      <tr><td>What we worked it out at</td>
          <td class="num r">{{ usd(c.requested) }}</td></tr>
      {% if c.is_approved %}
      <tr><td>Trimmed to your {{ usd(p.coverage_limit) }} episode cap</td>
          <td class="num r">&minus;{{ usd(trimmed) }}</td></tr>
      <tr><td>Your deductible</td>
          <td class="num r">&minus;{{ usd(p.deductible) }}</td></tr>
      {% else %}
      <tr><td colspan="2"><span class="tag no">{{ c.reason }}</span></td></tr>
      {% endif %}
      <tr><td><strong>Paid to you</strong></td>
          <td class="num r"><strong>{{ usd(c.approved) }}</strong></td></tr>
    </table></div>
  </div>

  <p class="muted">It goes on the record either way.</p>
  <div class="actions">
    <a class="btn ghost" href="{{ url_for('history', policy_id=p.policy_id) }}">[[icon:back]] Policy {{ p.policy_id }}</a>
    <a href="{{ url_for('claims') }}">Browse all claims</a>
  </div>
</div>
""")

CLAIMS = page("Claims &middot; Brain Freeze", "claims", """
<div class="wrap">
  <h1>Claims</h1>
  <p class="sub">{{ summary.claims }} claims on the book: {{ summary.approved }}
    approved, {{ summary.refused }} refused. Newest first.</p>
  <form method="get" action="{{ url_for('claims') }}" class="card search">
    <label for="q" class="q" style="margin:0">Find a claim</label>
    <input type="text" id="q" name="q" value="{{ wanted }}"
           placeholder="CLM-001285 or BF-100539" autocomplete="off">
    <button type="submit">Search</button>
    {% if wanted %}<a href="{{ url_for('claims') }}">clear</a>{% endif %}
  </form>
  <div class="card">
    <div class="filters">
      {% for value, label in filters %}
      <a class="tag{% if value == status %} on{% endif %}"
         href="{{ url_for('claims', status=value, q=wanted or None) }}">{{ label }}</a>
      {% endfor %}
    </div>
    {% if rows %}
    <div class="table-wrap"><table>
      <thead><tr><th>Claim</th><th>Episode</th><th>Policy</th><th>Treat</th>
          <th>Outcome</th><th class="r">Assessed</th><th class="r">Paid</th></tr></thead>
      <tbody>
      {% for c, e, p in rows %}
      <tr>
        <td><a class="id" href="{{ url_for('decision', policy_id=p.policy_id, claim_id=c.claim_id) }}">{{ c.claim_id }}</a></td>
        <td class="num">{{ e.event_date }}</td>
        <td><a class="id" href="{{ url_for('history', policy_id=p.policy_id) }}">{{ p.policy_id }}</a>
          <div class="muted">{{ p.plan_name }}</div></td>
        <td>{{ e.trigger }}</td>
        <td>{% if c.is_approved %}<span class="tag ok">Approved</span>
            {% else %}<span class="tag no">Refused</span>
            <div class="muted">{{ c.reason }}</div>{% endif %}</td>
        <td class="num r">{{ usd(c.requested) }}</td>
        <td class="num r">{{ usd(c.approved) }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table></div>
    """ + _PAGER + """
    {% else %}
    <p class="muted">No claims match{% if wanted %} &ldquo;{{ wanted }}&rdquo;{% endif %}.</p>
    {% endif %}
  </div>
</div>
""")
