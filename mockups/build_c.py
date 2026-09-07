# Direction C applied to all nine screens: rounded, bright, oversized.
# Single-form quote (not one-question-per-screen).
import io

BG='#d8ecf7'; INK='#10243a'; MUTED='#3f5f7a'; AC='#0e6ba8'; ACD='#084d7a'
SOFT='#eaf6fd'; LINE='#c3dced'; SH='0 3px 0 #b9d9ec'
GN='#12855f'; GND='#0b5e43'; GNS='#e2f4ec'
RD='#c4442a'; RDD='#8a2c17'; RDS='#fdeae5'

HELMET = f"""<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito+Sans:wght@400;600;700;800&display=swap">
  <style>
    body {{ margin: 0; font-family: 'Nunito Sans', system-ui, -apple-system, sans-serif;
           color: {INK}; background: {BG}; -webkit-font-smoothing: antialiased; }}
    a {{ color: {AC}; text-decoration: none; font-weight: 700; }}
    a:hover {{ color: {ACD}; text-decoration: underline; }}
    .rnd {{ font-family: 'Baloo 2', 'Nunito Sans', system-ui, sans-serif; }}
    .num {{ font-variant-numeric: tabular-nums }}
    .hint {{ font-size: 14px; color: {MUTED}; line-height: 1.55; font-weight: 600 }}
    .card {{ background: #fff; border-radius: 22px; box-shadow: {SH} }}
    .lbl {{ font-family: 'Baloo 2', 'Nunito Sans', sans-serif; font-size: 21px; font-weight: 700; color: {INK} }}
    .opt {{ display: flex; align-items: center; gap: 12px; background: #fff; border: 3px solid #fff;
           border-radius: 16px; padding: 0 18px; min-height: 60px; font-size: 17px; font-weight: 700;
           color: {INK}; box-shadow: {SH}; text-align: left }}
    .opt-on {{ border-color: {AC}; background: {SOFT}; box-shadow: 0 3px 0 {AC} }}
    .dot {{ width: 22px; height: 22px; border-radius: 50%; border: 3px solid {LINE}; flex-shrink: 0 }}
    .dot-on {{ border-color: {AC}; background: {AC}; box-shadow: inset 0 0 0 3px {SOFT} }}
    .btn {{ font-family: 'Baloo 2', 'Nunito Sans', sans-serif; display: inline-flex; align-items: center;
           justify-content: center; min-height: 60px; padding: 0 32px; background: {AC}; color: #fff;
           border-radius: 18px; font-size: 22px; font-weight: 700; box-shadow: 0 4px 0 {ACD} }}
    .btn2 {{ font-family: 'Baloo 2', 'Nunito Sans', sans-serif; display: inline-flex; align-items: center;
            justify-content: center; min-height: 60px; padding: 0 26px; background: #fff; color: {INK};
            border-radius: 18px; font-size: 20px; font-weight: 700; box-shadow: {SH} }}
    .tag {{ display: inline-flex; align-items: center; gap: 7px; border-radius: 999px; padding: 6px 14px;
           font-size: 14px; font-weight: 800 }}
    .new {{ display: inline-flex; align-items: center; background: {AC}; color: #fff; font-size: 12px;
           font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 9px; border-radius: 7px }}
  </style>
</helmet>"""

FLAKE = ('<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round">'
         '<path d="M12 2.5v19"/><path d="M3.8 7.2l16.4 9.6"/><path d="M20.2 7.2L3.8 16.8"/>'
         '<path d="M12 6.6l2.3-2.3M12 6.6L9.7 4.3M12 17.4l2.3 2.3M12 17.4l-2.3 2.3"/></svg>')

def shell(active, body, maxw=680):
    nav = []
    for name in ('Get a quote', 'File a claim', 'My policy'):
        on = (name == active)
        nav.append(f'<a href="#" style="font-size: 15px; padding: 9px 15px; border-radius: 12px;'
                   f'{" background: "+SOFT+"; color: "+ACD if on else " color: "+MUTED}">{name}</a>')
    return f"""<div style="display: flex; flex-direction: column; min-height: 100%; background: {BG}; position: relative; overflow: hidden">

  <div style="position: absolute; top: -90px; right: -70px; width: 300px; height: 300px; border-radius: 50%; background: #c9e6f6"></div>
  <div style="position: absolute; bottom: -110px; left: -80px; width: 360px; height: 360px; border-radius: 50%; background: #cde9f7"></div>

  <div style="position: relative; padding: 20px 40px 0">
    <div class="card" style="display: flex; align-items: center; justify-content: space-between; padding: 14px 22px; border-radius: 20px">
      <div style="display: flex; align-items: center; gap: 11px">
        {FLAKE % AC}
        <span class="rnd" style="font-weight: 800; font-size: 23px; letter-spacing: -0.01em">Brain&nbsp;Freeze</span>
      </div>
      <div style="display: flex; gap: 6px; align-items: center">{''.join(nav)}</div>
    </div>
  </div>

  <div style="position: relative; display: flex; flex-direction: column; align-items: center; padding: 34px 40px 56px">
    <div style="width: 100%; max-width: {maxw}px; display: flex; flex-direction: column; gap: 26px">
{body}
    </div>
  </div>

  <div style="position: relative; text-align: center; padding: 0 40px 18px">
    <span style="font-size: 13px; font-weight: 700; color: {MUTED}">Sample application &mdash; every policy and claim here lives in a GemDB database.</span>
  </div>
</div>"""

def page(name, body, maxw=680, active=''):
    doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
{HELMET}

{shell(active, body, maxw)}
</x-dc>
</body>
</html>
"""
    open(name, 'w').write(doc)
    return len(doc)

def h1(text, sub=None, size=48):
    s = f'      <div style="display: flex; flex-direction: column; gap: 10px">\n'
    s += f'        <h1 class="rnd" style="margin: 0; font-size: {size}px; line-height: 1.04; font-weight: 800; letter-spacing: -0.02em; text-wrap: pretty">{text}</h1>\n'
    if sub:
        s += f'        <p class="hint" style="margin: 0; font-size: 17px; max-width: 30em">{sub}</p>\n'
    return s + '      </div>\n'

def opts(items, cols=1, sel=None):
    """items: list of labels; sel: index or set of indices"""
    sel = set() if sel is None else ({sel} if isinstance(sel, int) else set(sel))
    style = (f'display: grid; grid-template-columns: repeat({cols}, minmax(0, 1fr)); gap: 10px'
             if cols > 1 else 'display: flex; flex-direction: column; gap: 10px')
    out = [f'        <div style="{style}">']
    for i, label in enumerate(items):
        on = i in sel
        out.append(f'          <div class="opt{" opt-on" if on else ""}">'
                   f'<span class="dot{" dot-on" if on else ""}"></span><span>{label}</span></div>')
    out.append('        </div>')
    return '\n'.join(out) + '\n'

def field(label, inner, hint=None, badge=False):
    s = '      <div style="display: flex; flex-direction: column; gap: 11px">\n'
    s += '        <div style="display: flex; align-items: center; gap: 10px">'
    badge_html = '<span class="new">New</span>' if badge else ''
    s += f'<span class="lbl">{label}</span>{badge_html}</div>\n'
    s += inner
    if hint:
        s += f'        <span class="hint">{hint}</span>\n'
    return s + '      </div>\n'

# ---------------------------------------------------------------- 0 · Picker
POLICIES = [
    ("BF-100000", 15, "Medium", "Premium",  "$170.10", 7, 2, "$133.07"),
    ("BF-100001", 17, "High",   "Premium",  "$341.26", 5, 3, "$138.26"),
    ("BF-100002", 13, "Low",    "Basic",    "$30.36",  4, 0, None),
    ("BF-100003", 10, "Medium", "Standard", "$88.62",  2, 2, "$64.51"),
    ("BF-100004", 11, "High",   "Standard", "$190.10", 7, 3, "$146.60"),
    ("BF-100005", 12, "High",   "Standard", "$179.38", 8, 4, "$175.98"),
]
TIER = {"High": (RDS, RDD), "Medium": ("#eef2f6", MUTED), "Low": (GNS, GND)}

cards = []
for pid, age, tier, plan, prem, ev, cl, paid in POLICIES:
    bg, fg = TIER[tier]
    cards.append(f"""        <div class="card" style="padding: 20px 22px; display: flex; flex-direction: column; gap: 13px">
          <div style="display: flex; align-items: center; justify-content: space-between">
            <span class="rnd num" style="font-size: 22px; font-weight: 800">{pid}</span>
            <span class="tag" style="background: {bg}; color: {fg}">{tier}</span>
          </div>
          <div style="display: flex; flex-direction: column; gap: 3px">
            <span style="font-size: 15px; font-weight: 700; color: {INK}">Age {age} &middot; {plan}</span>
            <span class="hint num" style="font-size: 13.5px">{prem} a year &middot; {ev} treats &middot; {cl} claim{'' if cl==1 else 's'}</span>
            <span class="hint num" style="font-size: 13.5px">{('Paid out ' + paid) if paid else 'Never claimed'}</span>
          </div>
          <div class="btn2" style="min-height: 50px; font-size: 18px; box-shadow: 0 3px 0 {LINE}">Act as this one</div>
        </div>""")

body = h1("Who are you<br>today?",
          "No sign-in here. Step into any of the 900 policyholders already in the database, or start a brand new policy of your own.", 52)
body += f"""      <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px">
{chr(10).join(cards)}
      </div>

      <div class="card" style="padding: 22px 26px; display: flex; align-items: center; justify-content: space-between; gap: 24px; background: {SOFT}; box-shadow: 0 3px 0 {LINE}">
        <div style="display: flex; flex-direction: column; gap: 4px">
          <span class="rnd" style="font-size: 24px; font-weight: 800">Or start from nothing</span>
          <span class="hint">Answer five questions and take out policy number 901.</span>
        </div>
        <div class="btn" style="min-height: 54px; font-size: 20px; white-space: nowrap">Get a quote</div>
      </div>

      <span class="hint" style="font-size: 13.5px">Showing six of 900. Whoever you pick, the notebook and agent mode are looking at the same objects.</span>
"""
print("Picker", page("Picker.dc.html", body, 900))

# ------------------------------------------------------------------ 1 · Quote
body  = h1("Let's price<br>the freeze.", "Five questions about the person you want covered. Nothing is charged until you pick a plan.", 52)
body += '      <div class="card" style="padding: 30px 32px; display: flex; flex-direction: column; gap: 28px">\n'
body += field("How old are they?",
    f'        <div style="display: flex; align-items: center; gap: 14px">\n'
    f'          <div class="card num rnd" style="width: 130px; min-height: 60px; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 800; background: {SOFT}; box-shadow: 0 3px 0 {LINE}">11</div>\n'
    f'          <span class="hint">Cover runs from 5 to 19.</span>\n        </div>\n')
body += field("Any migraine diagnosis?", opts(["Yes", "No"], 2, 1))
body += field("Any tension-headache diagnosis?", opts(["Yes", "No"], 2, 1))
body += field("How fast do they get through something cold?",
              opts(["Slowly, one sip at a time", "About normal", "All of it, immediately"], 1, 2),
              "This one moves the price more than anything else.")
body += field("What do they reach for most?",
              opts(["Ice cream", "Slushie", "Popsicle", "Iced soda", "Smoothie", "Cold plunge"], 2, 1))
body += '      </div>\n'
body += f"""      <div style="display: flex; align-items: center; gap: 20px">
        <div class="btn">See the plans</div>
        <span class="hint" style="max-width: 20em">No account, no card, nothing saved until you say yes.</span>
      </div>
"""
print("Quote", page("Main.dc.html", body, 680, 'Get a quote'))

# ------------------------------------------------------------------ 2 · Plans
PLANS = [
    ("Basic",    "$7.12",  "$85.50",  "$25",  "$10",   False),
    ("Standard", "$14.25", "$171.00", "$60",  "$5",    True),
    ("Premium",  "$28.50", "$342.00", "$150", "none",  False),
]
pc = []
for nm, mo, yr, lim, ded, best in PLANS:
    edge = f'box-shadow: 0 5px 0 {ACD}; border: 4px solid {AC}' if best else f'box-shadow: {SH}; border: 4px solid #fff'
    pc.append(f"""        <div class="card" style="padding: 24px 22px; display: flex; flex-direction: column; gap: 15px; {edge}; position: relative">
          {'<span class="tag" style="position: absolute; top: -15px; left: 20px; background: '+AC+'; color: #fff">Most picked</span>' if best else ''}
          <span class="rnd" style="font-size: 26px; font-weight: 800">{nm}</span>
          <div style="display: flex; align-items: baseline; gap: 5px">
            <span class="rnd num" style="font-size: 42px; font-weight: 800; letter-spacing: -0.025em; line-height: 1">{mo}</span>
            <span class="hint" style="font-size: 15px">/ mo</span>
          </div>
          <span class="hint num" style="font-size: 13.5px; margin-top: -10px">{yr} a year</span>
          <div style="height: 3px; background: {SOFT}; border-radius: 2px"></div>
          <div style="display: flex; flex-direction: column; gap: 9px; font-size: 15px; font-weight: 700">
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Per episode</span><span class="num">{lim}</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Deductible</span><span class="num">{ded}</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Claims a year</span><span class="num">4</span></div>
          </div>
          <div class="{'btn' if best else 'btn2'}" style="min-height: 54px; font-size: 19px; margin-top: auto{'' if best else '; box-shadow: 0 3px 0 '+LINE}">Pick {nm}</div>
        </div>""")

body  = h1("You're a 75.", "Age 11, eats fast, loves a slushie, no headache history. That lands in the High band &mdash; here is what it costs.", 50)
body += f"""      <div class="card" style="padding: 26px 28px; display: flex; align-items: center; gap: 30px">
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; flex-shrink: 0">
          <span class="rnd num" style="font-size: 68px; font-weight: 800; line-height: 0.95; letter-spacing: -0.03em; color: {AC}">75</span>
          <span class="tag" style="background: {RDS}; color: {RDD}">High band</span>
        </div>
        <div style="width: 3px; align-self: stretch; background: {SOFT}; border-radius: 2px"></div>
        <div style="flex-grow: 1; display: flex; flex-direction: column; gap: 10px">
          <span class="lbl" style="font-size: 19px">Where it came from</span>
          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 15.5px; font-weight: 700">
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Everyone starts here</span><span class="num">45</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Eats it all immediately</span><span class="num" style="color: {RDD}">+18</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Slushies are the worst offender</span><span class="num" style="color: {RDD}">+12</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Age 11, no headache history</span><span class="num">0</span></div>
          </div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px">
{chr(10).join(pc)}
      </div>

      <span class="hint" style="font-size: 13.5px">The High band nearly doubles the base rate. A Low-band 16-year-old who sips a smoothie pays $31.50, $63.00 or $126.00 a year.</span>
"""
print("Plans", page("Plans.dc.html", body, 880, 'Get a quote'))

# --------------------------------------------------------------- 3 · Accepted
body  = f"""      <div style="display: flex; align-items: center; gap: 18px">
        <div style="display: flex; align-items: center; justify-content: center; width: 68px; height: 68px; border-radius: 50%; background: {GN}; box-shadow: 0 4px 0 {GND}; flex-shrink: 0">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
        </div>
        <h1 class="rnd" style="margin: 0; font-size: 48px; line-height: 1.02; font-weight: 800; letter-spacing: -0.02em">You're covered!</h1>
      </div>

      <div class="card" style="padding: 28px 30px; display: flex; align-items: center; justify-content: space-between; gap: 26px; background: {SOFT}; box-shadow: 0 3px 0 {LINE}">
        <div style="display: flex; flex-direction: column; gap: 5px">
          <span class="hint" style="font-size: 13.5px; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 800">Your policy number</span>
          <span class="rnd num" style="font-size: 40px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">BF-100900</span>
          <span class="hint" style="font-size: 13.5px">Quote it when you claim. There is nothing to log in to.</span>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0">
          <span class="rnd num" style="font-size: 36px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">$14.25</span>
          <span class="hint" style="font-size: 13.5px">a month</span>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px">
        <div class="card" style="padding: 22px 24px; display: flex; flex-direction: column; gap: 13px">
          <span class="lbl" style="font-size: 19px">What you get</span>
          <div style="display: flex; flex-direction: column; gap: 9px; font-size: 15.5px; font-weight: 700">
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Per episode</span><span class="num">up to $60</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Deductible</span><span class="num">$5</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Claims a year</span><span class="num">4</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Runs until</span><span class="num">7 Sep 2027</span></div>
          </div>
        </div>
        <div class="card" style="padding: 22px 24px; display: flex; flex-direction: column; gap: 13px">
          <span class="lbl" style="font-size: 19px">What you told us</span>
          <div style="display: flex; flex-direction: column; gap: 9px; font-size: 15.5px; font-weight: 700">
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Age</span><span class="num">11</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Headaches</span><span>none</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Pace</span><span>immediate</span></div>
            <div style="display: flex; justify-content: space-between"><span class="hint" style="font-weight: 600">Favourite</span><span>slushie</span></div>
          </div>
        </div>
      </div>

      <div style="display: flex; align-items: center; gap: 14px">
        <div class="btn">See my policy</div>
        <div class="btn2" style="box-shadow: 0 3px 0 {LINE}">File a claim</div>
      </div>

      <div class="card" style="display: flex; gap: 13px; padding: 18px 20px; background: #fff">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{AC}" stroke-width="2.2" stroke-linecap="round" style="flex-shrink: 0; margin-top: 1px"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg>
        <span class="hint" style="font-size: 14.5px">Policy 900 follows the 900 already in the database &mdash; a new object in the same collection, committed. Refresh the notebook and it is there.</span>
      </div>
"""
print("Accepted", page("Accepted.dc.html", body, 680, 'My policy'))

# ------------------------------------------------- 4 & CUJ-4 · the claim form
def claim_form(v2=False):
    strip = f"""      <div class="card" style="padding: 16px 22px; display: flex; align-items: center; gap: 18px; flex-wrap: wrap; background: {SOFT}; box-shadow: 0 3px 0 {LINE}">
        <span class="rnd num" style="font-size: 20px; font-weight: 800">{'BF-100900' if v2 else 'BF-100023'}</span>
        <span class="hint" style="font-size: 14px">Standard &middot; {'High' if v2 else 'Medium'} band &middot; $60 an episode, $5 deductible</span>
        <span class="tag" style="background: #fff; color: {RDD if not v2 else MUTED}; margin-left: auto">{'0' if v2 else '3'} of 4 claims used</span>
      </div>
"""
    b = strip + h1("What happened?", "Tell us about the episode. We work out the money from your answers &mdash; there is no figure to type in.", 48)
    b += '      <div class="card" style="padding: 30px 32px; display: flex; flex-direction: column; gap: 28px">\n'
    if v2:
        b += f"""        <div style="display: flex; gap: 13px; padding: 18px 20px; background: {SOFT}; border-radius: 16px">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{AC}" stroke-width="2.4" stroke-linecap="round" style="flex-shrink: 0; margin-top: 1px"><path d="M12 5v14M5 12h14"/></svg>
          <span style="font-size: 14.5px; font-weight: 700; color: {ACD}; line-height: 1.55">Two questions added. Flavour and toppings went in after 900 policies and 5,017 episodes were already committed &mdash; no migration, nothing rewritten. Older claims just have no flavour.</span>
        </div>
"""
    treat = ["Ice cream", "Slushie", "Popsicle", "Iced soda", "Smoothie", "Cold plunge"]
    b += field("What did they have?", opts(treat, 2, 0 if v2 else 3))
    b += field("How cold was it?",
               opts(["Straight from the freezer", "Iced", "Fridge-cold", "Cool"], 2, 0 if v2 else 1),
               "A band, not a reading &mdash; nobody owns a thermometer for this.")
    b += field("How much of it?", opts(["A few sips", "Small", "Regular", "A lot"], 2, 1))
    b += field("How fast?", opts(["Slowly", "About normal", "All at once"], 1, 1))
    scale = ['        <div style="display: grid; grid-template-columns: repeat(11, minmax(0, 1fr)); gap: 6px">']
    for i in range(11):
        on = (i == 5)
        scale.append(f'          <div class="rnd" style="display: flex; align-items: center; justify-content: center; min-height: 52px; '
                     f'border-radius: 13px; font-size: 19px; font-weight: 800; '
                     f'{"background: "+AC+"; color: #fff; box-shadow: 0 3px 0 "+ACD if on else "background: #fff; color: "+MUTED+"; box-shadow: "+SH}">{i}</div>')
    scale.append('        </div>')
    b += field("How bad was it?", '\n'.join(scale) + '\n',
               f'<span style="color: {ACD}">Moderate</span> &mdash; 0 is barely noticed, 10 is the worst they can imagine.')
    b += field("How long did it last?", opts(["Under 30 seconds", "Half a minute to two", "Two to ten minutes", "Longer than ten"], 2, 2))
    b += field("Where did it hurt?", opts(["Forehead", "Temple", "Back of the head", "All over"], 2, 0))
    b += field("What did it feel like?", opts(["Stabbing", "Pulling", "Dull and pressing"], 1, 2 if v2 else 2))
    if v2:
        b += field("Which flavour?", opts(["Vanilla", "Chocolate", "Strawberry", "Mint choc chip", "Cookie dough", "Something else"], 2, 3), badge=True)
        b += field("Anything on top?", opts(["Sprinkles", "Hot fudge", "Whipped cream", "Nuts", "Cherry", "Nothing"], 2, [0, 1]),
                   "Pick as many as apply. Stored as a list on the claim.", badge=True)
    b += '      </div>\n'
    b += f"""      <div style="display: flex; align-items: center; gap: 20px">
        <div class="btn">Send the claim</div>
        <span class="hint" style="max-width: 20em">You get the answer straight away.</span>
      </div>
"""
    return b

print("FileClaim", page("FileClaim.dc.html", claim_form(False), 680, 'File a claim'))
print("ClaimV2",   page("ClaimV2.dc.html",   claim_form(True),  680, 'File a claim'))

# --------------------------------------------------------------- 5 · Decision
body = f"""      <div class="card" style="overflow: hidden; padding: 0">
        <div style="background: {GN}; padding: 30px 32px; display: flex; align-items: center; gap: 18px">
          <div style="display: flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 50%; background: rgba(255,255,255,0.22); flex-shrink: 0">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>
          </div>
          <div style="display: flex; flex-direction: column; gap: 2px">
            <span class="rnd num" style="font-size: 38px; font-weight: 800; color: #fff; letter-spacing: -0.02em; line-height: 1.05">$55.00 is yours</span>
            <span class="num" style="font-size: 14.5px; font-weight: 700; color: #cfeade">CLM-000059 &middot; iced soda &middot; 24 October 2026</span>
          </div>
        </div>
        <div style="padding: 24px 32px 28px; display: flex; flex-direction: column; gap: 11px">
          <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 700"><span class="hint" style="font-weight: 600">What we worked it out at</span><span class="num">$62.77</span></div>
          <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 700"><span class="hint" style="font-weight: 600">Trimmed to your $60 episode cap</span><span class="num" style="color: {RDD}">&minus;$2.77</span></div>
          <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 700"><span class="hint" style="font-weight: 600">Your deductible</span><span class="num" style="color: {RDD}">&minus;$5.00</span></div>
          <div style="height: 3px; background: {SOFT}; border-radius: 2px; margin: 4px 0"></div>
          <div style="display: flex; justify-content: space-between; align-items: baseline"><span class="rnd" style="font-size: 22px; font-weight: 800">Paid to you</span><span class="rnd num" style="font-size: 30px; font-weight: 800">$55.00</span></div>
          <div style="display: flex; gap: 12px; padding: 16px 18px; background: {SOFT}; border-radius: 15px; margin-top: 8px">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{AC}" stroke-width="2.2" stroke-linecap="round" style="flex-shrink: 0; margin-top: 1px"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg>
            <span class="hint" style="font-size: 14.5px; color: {ACD}">That was claim four of four for this year. The next one gets turned down until 3 February 2027.</span>
          </div>
        </div>
      </div>

      <div class="card" style="overflow: hidden; padding: 0">
        <div style="background: {RD}; padding: 30px 32px; display: flex; align-items: center; gap: 18px">
          <div style="display: flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 50%; background: rgba(255,255,255,0.22); flex-shrink: 0">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </div>
          <div style="display: flex; flex-direction: column; gap: 2px">
            <span class="rnd" style="font-size: 38px; font-weight: 800; color: #fff; letter-spacing: -0.02em; line-height: 1.05">Not this time</span>
            <span class="num" style="font-size: 14.5px; font-weight: 700; color: #f7d8ce">CLM-000060 &middot; smoothie &middot; 6 November 2026</span>
          </div>
        </div>
        <div style="padding: 24px 32px 28px; display: flex; flex-direction: column; gap: 16px">
          <span class="rnd" style="font-size: 21px; font-weight: 700; line-height: 1.35">You have already had four claims paid this year, and four is the limit on every plan.</span>
          <div style="display: flex; flex-direction: column; gap: 11px">
            <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 700"><span class="hint" style="font-weight: 600">What we worked it out at</span><span class="num">$38.68</span></div>
            <div style="display: flex; justify-content: space-between; font-size: 16px; font-weight: 700"><span class="hint" style="font-weight: 600">Claims used</span><span class="num">4 of 4</span></div>
            <div style="height: 3px; background: {SOFT}; border-radius: 2px; margin: 4px 0"></div>
            <div style="display: flex; justify-content: space-between; align-items: baseline"><span class="rnd" style="font-size: 22px; font-weight: 800">Paid to you</span><span class="rnd num" style="font-size: 30px; font-weight: 800">$0.00</span></div>
          </div>
          <span class="hint" style="font-size: 14.5px">It still goes on your record &mdash; it just is not paid.</span>
          <a href="#" style="font-size: 16px">See everything on my policy</a>
        </div>
      </div>
"""
print("Decision", page("Decision.dc.html", body, 680, 'File a claim'))

# ---------------------------------------------------------------- 6 · History
EVENTS = [
    ("18 Feb 2026", "Iced soda",  "Iced",            None, None,  None,          None),
    ("25 Apr 2026", "Popsicle",   "From the freezer", 2,   "20s", None,          None),
    ("31 May 2026", "Ice cream",  "From the freezer", 3,   "9m",  "CLM-000056",  "$55.00"),
    ("1 Jun 2026",  "Iced soda",  "Cool",             5,   "13s", "CLM-000057",  "$32.70"),
    ("6 Aug 2026",  "Slushie",    "Iced",             3,   "7m",  "CLM-000058",  "$50.73"),
    ("19 Sep 2026", "Smoothie",   "Fridge-cold",     None, None,  None,          None),
    ("18 Oct 2026", "Popsicle",   "From the freezer", 3,   "20s", None,          None),
    ("24 Oct 2026", "Iced soda",  "Iced",             5,   "9m",  "CLM-000059",  "$55.00"),
    ("6 Nov 2026",  "Smoothie",   "Cool",             5,   "22s", "CLM-000060",  "declined"),
]
rows = []
for date, treat, cold, nrs, dur, clm, amt in EVENTS:
    if amt == "declined":
        right = f'<span class="tag" style="background: {RDS}; color: {RDD}">Turned down</span>'
    elif amt:
        right = f'<span class="rnd num" style="font-size: 22px; font-weight: 800; color: {GND}">{amt}</span>'
    elif nrs is None:
        right = f'<span class="tag" style="background: #eef2f6; color: {MUTED}">No headache</span>'
    else:
        right = f'<span class="tag" style="background: #eef2f6; color: {MUTED}">Not claimed</span>'
    detail = f'{cold}' + (f' &middot; pain {nrs} &middot; {dur}' if nrs is not None else '')
    rows.append(f"""        <div style="display: flex; align-items: center; gap: 18px; padding: 15px 20px; background: #fff; border-radius: 16px; box-shadow: {SH}">
          <div style="display: flex; flex-direction: column; gap: 2px; width: 118px; flex-shrink: 0">
            <span class="num" style="font-size: 14.5px; font-weight: 800">{date}</span>
            {'<span class="hint num" style="font-size: 12.5px">'+clm+'</span>' if clm else ''}
          </div>
          <div style="display: flex; flex-direction: column; gap: 2px; flex-grow: 1; min-width: 0">
            <span class="rnd" style="font-size: 19px; font-weight: 700">{treat}</span>
            <span class="hint" style="font-size: 13.5px">{detail}</span>
          </div>
          {right}
        </div>""")

STATS = [("9", "cold treats"), ("7", "gave a headache"), ("5", "claims sent"), ("$193.43", "paid out"), ("4/4", "claims used")]
tiles = []
for big, small in STATS:
    tiles.append(f"""        <div class="card" style="padding: 18px 20px; display: flex; flex-direction: column; gap: 4px">
          <span class="rnd num" style="font-size: 30px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">{big}</span>
          <span class="hint" style="font-size: 13px">{small}</span>
        </div>""")

body = f"""      <div class="card" style="padding: 26px 30px; display: flex; align-items: center; justify-content: space-between; gap: 30px">
        <div style="display: flex; flex-direction: column; gap: 9px">
          <div style="display: flex; align-items: center; gap: 13px">
            <span class="rnd num" style="font-size: 38px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">BF-100023</span>
            <span class="tag" style="background: {GNS}; color: {GND}">Active</span>
          </div>
          <span class="hint" style="font-size: 15px">Standard &middot; Medium band, 44.8 &middot; $60 an episode, $5 deductible</span>
          <span class="hint num" style="font-size: 13.5px">Year started 3 February 2026, renews 3 February 2027</span>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 1px; flex-shrink: 0">
          <span class="rnd num" style="font-size: 34px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">$7.82</span>
          <span class="hint" style="font-size: 13.5px">a month</span>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 13px">
{chr(10).join(tiles)}
      </div>

      <div style="display: flex; flex-direction: column; gap: 12px">
        <span class="lbl" style="font-size: 22px">Every cold treat on record</span>
{chr(10).join(rows)}
      </div>

      <span class="hint" style="font-size: 13.5px; max-width: 46em">The ones that gave no headache are on here too. They are the denominator &mdash; without them, how often a slushie causes brain freeze is not a question the data can answer.</span>
"""
print("History", page("History.dc.html", body, 820, 'My policy'))

# ----------------------------------------------------------- 6b · Empty state
etiles = []
for big, small in [("0", "cold treats"), ("0", "gave a headache"), ("0", "claims sent"), ("$0.00", "paid out"), ("0/4", "claims used")]:
    etiles.append(f"""        <div class="card" style="padding: 18px 20px; display: flex; flex-direction: column; gap: 4px">
          <span class="rnd num" style="font-size: 30px; font-weight: 800; letter-spacing: -0.02em; line-height: 1; color: #a9bfd0">{big}</span>
          <span class="hint" style="font-size: 13px">{small}</span>
        </div>""")

body = f"""      <div class="card" style="padding: 26px 30px; display: flex; align-items: center; justify-content: space-between; gap: 30px">
        <div style="display: flex; flex-direction: column; gap: 9px">
          <div style="display: flex; align-items: center; gap: 13px">
            <span class="rnd num" style="font-size: 38px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">BF-100900</span>
            <span class="tag" style="background: {GNS}; color: {GND}">Active</span>
          </div>
          <span class="hint" style="font-size: 15px">Standard &middot; High band, 75.0 &middot; $60 an episode, $5 deductible</span>
          <span class="hint num" style="font-size: 13.5px">Started today, renews 7 September 2027</span>
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 1px; flex-shrink: 0">
          <span class="rnd num" style="font-size: 34px; font-weight: 800; letter-spacing: -0.02em; line-height: 1">$14.25</span>
          <span class="hint" style="font-size: 13.5px">a month</span>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 13px">
{chr(10).join(etiles)}
      </div>

      <div class="card" style="padding: 66px 40px; display: flex; flex-direction: column; align-items: center; gap: 20px; text-align: center">
        {FLAKE.replace('width="26" height="26"', 'width="72" height="72"') % '#c3dced'}
        <div style="display: flex; flex-direction: column; gap: 10px; align-items: center">
          <span class="rnd" style="font-size: 32px; font-weight: 800; letter-spacing: -0.02em">Nothing yet!</span>
          <span class="hint" style="max-width: 30em; font-size: 15.5px">Log a cold treat whether or not it hurt. The ones that did not are how we work out how often they do.</span>
        </div>
        <div class="btn" style="margin-top: 4px">Log the first one</div>
      </div>
"""
print("EmptyHistory", page("EmptyHistory.dc.html", body, 820, 'My policy'))
