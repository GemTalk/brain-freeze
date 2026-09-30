"""The questions the app asks, and the one place an answer is read.

`answers_from(mapping)` is the single reader for both surfaces: it takes
anything with `.get`, which a Flask form and a decoded JSON body both are.

The vocabulary the risk model owns is imported rather than restated; this
module supplies only the labels a person reads.
"""

from brainfreeze import CONSUMPTION_SPEEDS, TRIGGER_TYPES

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
DURATION_BANDS = [
    ("Under 30 seconds", 20.0),
    ("Half a minute to two", 70.0),
    ("Two to ten minutes", 300.0),
    ("Longer than ten", 700.0),
]
PAIN_LOCATIONS = ["Forehead", "Temple", "Back of the head", "All over"]
PAIN_QUALITIES = ["Stabbing", "Pulling", "Dull and pressing"]

#: Labels for the speeds the risk model defines, not a second list of speeds.
SPEED_LABELS = {"slow": "Slowly", "moderate": "About normal",
                "fast": "All at once"}
SPEED_BANDS = [(SPEED_LABELS[speed], speed) for speed in CONSUMPTION_SPEEDS]

#: If the model gains a speed, this fails at import rather than rendering a
#: form that quietly omits an option.
assert set(SPEED_LABELS) == set(CONSUMPTION_SPEEDS), (
    "forms.py has labels for %s but the risk model knows %s"
    % (sorted(SPEED_LABELS), sorted(CONSUMPTION_SPEEDS)))

TRIGGERS = TRIGGER_TYPES

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


def quote_questions():
    """The five quote questions as data, for `/api/questions`.

    Built from the same constants the HTML form loops over, so the two
    surfaces ask the same things and a caller reads exactly the answers
    `/api/quote` accepts.

    Sex is not asked, here or on the form: the risk model gives it no
    weight.
    """
    return [
        {"name": "age", "prompt": "How old are they?",
         "type": "integer", "minimum": 5, "maximum": 19, "default": 11},
        {"name": "migraine_history", "prompt": "Diagnosed with migraine?",
         "type": "boolean", "default": False},
        {"name": "tension_type_headache_history",
         "prompt": "Diagnosed with tension headaches?",
         "type": "boolean", "default": False},
        {"name": "typical_consumption_speed",
         "prompt": "How fast do they usually eat something cold?",
         "type": "choice", "default": "moderate",
         "options": [{"label": label, "value": value}
                     for label, value in SPEED_BANDS]},
        {"name": "favourite_trigger", "prompt": "Favourite cold treat",
         "type": "choice", "default": TRIGGERS[0],
         "options": [{"label": name, "value": name} for name in TRIGGERS]},
    ]


def _flag(value):
    """A JSON true/false, or the "yes"/"no" the HTML form would have sent."""
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "true", "1")
    return bool(value)


def answers_from(data):
    """The five answers out of anything with `.get`, or a ValueError.

    Checked here rather than left to `quote()`, which would meet an unknown
    trigger as a KeyError deep inside the risk model. The form sends
    "yes"/"no" where JSON sends true/false; `_flag` takes either.
    """
    try:
        age = int(data.get("age", 11))
    except (TypeError, ValueError):
        raise ValueError(
            "age must be a whole number, not %r" % (data.get("age"),))

    speeds = [value for _, value in SPEED_BANDS]
    speed = data.get("typical_consumption_speed", "moderate")
    if speed not in speeds:
        raise ValueError("typical_consumption_speed must be one of %s"
                         % ", ".join(speeds))

    trigger = data.get("favourite_trigger", TRIGGERS[0])
    if trigger not in TRIGGERS:
        raise ValueError("favourite_trigger must be one of %s"
                         % ", ".join(TRIGGERS))

    return dict(
        age=age,
        migraine_history=_flag(data.get("migraine_history", False)),
        tension_type_headache_history=_flag(
            data.get("tension_type_headache_history", False)),
        typical_consumption_speed=speed,
        favourite_trigger=trigger,
    )
