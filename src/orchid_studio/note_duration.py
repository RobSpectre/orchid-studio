"""orchid-robot score duration notation; quarter notes are beats, bars are 4/4."""
# A copy of orchid-robot's orchid_demo/music.py beats(), the source of truth: change that first, then this.
from fractions import Fraction
import math
import re


DEFAULT_DURATION = "1/8"
LETTERS = {"w": 4, "h": 2, "q": 1, "e": Fraction(1, 2), "s": Fraction(1, 4)}
NOTE = re.compile(r"^(?:(?P<letter>[whqes])|(?P<num>\d+)(?:/(?P<den>\d+))?)(?P<mod>[.t]?)$")
BARS = re.compile(r"^(?P<bars>\d+(?:\.\d+)?)\s*bars?$")
HOW = "duration must be a note value (1/4, 1/8., 1/8t, w/h/q/e/s), bars (2bars), or tied values (1bar+1/4)"


def duration_beats(value):
    """Match robot's score strings (including its 40-character API bound)."""
    if not isinstance(value, str) or not value.strip() or len(value) > 40:
        raise ValueError(HOW + "; use a string of 1–40 characters")
    total = Fraction(0)
    for part in value.split("+"):
        part = part.strip()
        bars = BARS.fullmatch(part)
        if bars:
            total += Fraction(bars["bars"]) * 4
            continue
        note = NOTE.fullmatch(part)
        if not note:
            raise ValueError(HOW)
        if note["letter"]:
            length = LETTERS[note["letter"]]
        else:
            denominator = int(note["den"] or 1)
            if denominator not in (1, 2, 4, 8, 16, 32, 64):
                raise ValueError("duration denominator must be 1, 2, 4, 8, 16, 32 or 64")
            length = Fraction(int(note["num"]) * 4, denominator)
        total += length * {"": 1, ".": Fraction(3, 2), "t": Fraction(2, 3)}[note["mod"]]
    beats = float(total)
    if not math.isfinite(beats) or beats <= 0:
        raise ValueError("duration must have a positive finite length")
    return beats
