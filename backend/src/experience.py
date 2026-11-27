"""Find a job posting's required years of experience in its text, without an LLM call.

`years_required(*texts)` returns a short label such as "3+ years" or "2-4 years" (or "" when
the text says nothing about it), which the ranking step reads next to each job so it can
score jobs that need far more experience than the user has as weak fits.

When a posting names several numbers ("2+ years of Python, 5+ years overall") the smallest
minimum is kept, so a job is never made to look more senior than its text supports.
"""

import re

_NUM = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen)"
_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
    "fifteen": 15,
}
_YEARS = r"\s*(?:\(\d{1,2}\)\s*)?(?:years?|yrs?)\b"
# Experience must follow within a few words ("5 years of hands-on product experience").
_OF_EXPERIENCE = r"(?=[^.;\n]{0,60}?\b(?:experience|exp\b|background|track record|working))"

_RANGE = re.compile(rf"\b{_NUM}\s*\+?\s*(?:-|–|—|to)\s*{_NUM}\s*\+?{_YEARS}", re.IGNORECASE)
_PLUS = re.compile(rf"\b{_NUM}\s*\+{_YEARS}", re.IGNORECASE)
_MINIMUM = re.compile(
    rf"\b(?:at\s+least|minimum(?:\s+of)?|min\.?|no\s+less\s+than|more\s+than|over)\s+{_NUM}"
    rf"\s*\+?{_YEARS}",
    re.IGNORECASE,
)
_PLAIN = re.compile(rf"\b{_NUM}{_YEARS}\s*(?:of\s+)?{_OF_EXPERIENCE}", re.IGNORECASE)
_MAX_YEARS = 25  # Larger numbers are company ages ("for 40 years"), not requirements.


def _number(text: str) -> int:
    return int(text) if text.isdigit() else _WORDS[text.lower()]


def years_required(*texts: str | None) -> str:
    """The least experience the texts ask for, as "N+ years" / "N-M years", or ""."""
    text = " ".join(t for t in texts if t)
    if not text:
        return ""
    found: list[tuple[int, int | None]] = []  # (minimum, maximum or None)
    for match in _RANGE.finditer(text):
        low, high = _number(match.group(1)), _number(match.group(2))
        if low < high <= _MAX_YEARS:
            found.append((low, high))
    spans = [m.span() for m in _RANGE.finditer(text)]
    for pattern in (_PLUS, _MINIMUM, _PLAIN):
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in spans):
                continue  # Already counted as part of a range.
            years = _number(match.group(1))
            if years <= _MAX_YEARS:
                found.append((years, None))
    if not found:
        return ""
    low, high = min(found, key=lambda item: (item[0], item[1] is not None))
    if high is not None:
        return f"{low}-{high} years"
    return f"{low}+ year" if low == 1 else f"{low}+ years"
