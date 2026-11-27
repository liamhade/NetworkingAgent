"""How much work experience a user's free-text background shows.

`user_years` is what `filter` compares postings' `years_required` against. Three signals, most
direct first:

1. a stated amount ("3 years of SQL"): the largest, up to 40;
2. work date ranges ("Software Engineer, Nov 2025 - present"): the months covered by roles
   that are not student roles (internships, assistantships, degrees, volunteering), overlaps
   counted once, up to today, in whole years;
3. only student date ranges, or student / new-grad wording ("recent graduate", "graduated
   June 2025"), and no work range: 0 years.

Everything here undercounts when unsure (a year without a month counts from mid-year, a line
that might be schooling is skipped), because the filter only drops jobs that ask for far more
experience than this number. No signal at all gives None, and nothing is dropped.
"""

import re
from datetime import date

from schemas import SearchRequest

_YEARS = re.compile(r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_DATE = r"(?:(?P<{n}m>[A-Za-z]{{3,9}})\.?,?\s+)?(?P<{n}y>(?:19|20)\d\d)"
_RANGE = re.compile(
    _DATE.format(n="s")
    + r"\s*(?:-|–|—|to|until)\s*(?:"
    + _DATE.format(n="e")
    + r"|(?P<now>present|current|now|today|ongoing|date))",
    re.IGNORECASE,
)
_NOT_WORK = re.compile(
    r"\b(intern(?:ship)?s?|student|teaching assistant|research assistant|co-?op|volunteer|"
    r"university|college|school|bachelor'?s?|master'?s?|b\.?[sa]\.?|m\.?[sa]\.?|ph\.?d|"
    r"degree|gpa|coursework|bootcamp|certificat\w*|expected|class of)\b",
    re.IGNORECASE,
)
_NEW_GRAD = re.compile(
    r"\b(students?|new[- ]?grad\w*|recent(?:ly)? grad\w*|graduat(?:e|ed|ing|ion)|"
    r"undergrad\w*|freshman|sophomore|class of|expected)\b",
    re.IGNORECASE,
)


def _month(label: str | None) -> int | None:
    if not label:
        return None
    key = label.lower()[:3]
    return _MONTHS.index(key) + 1 if key in _MONTHS else None


def _point(match: re.Match[str], name: str) -> tuple[int, int]:
    """(year, month) of one end of a range; a missing month is mid-year (July)."""
    year = int(match.group(f"{name}y"))
    return year, _month(match.group(f"{name}m")) or 7


def _work_intervals(text: str, today: date) -> tuple[list[tuple[int, int]], bool]:
    """Month-index intervals (year * 12 + month) of the non-student date ranges in `text`,
    and whether it also has student ranges (a degree, an internship)."""
    now = today.year * 12 + today.month
    lines = text.splitlines()
    found: list[tuple[int, int]] = []
    student = False
    for i, line in enumerate(lines):
        for match in _RANGE.finditer(line):
            context = line
            if len(_RANGE.sub("", line).split()) < 3 and i > 0:
                context = f"{lines[i - 1]} {line}"  # "Software Engineer" / "Nov 2025 - present"
            if _NOT_WORK.search(context):
                student = True
                continue
            sy, sm = _point(match, "s")
            start = sy * 12 + sm
            if match.group("now"):
                end = now
            else:
                ey, em = _point(match, "e")
                end = min(ey * 12 + em, now)
            if end > start:
                found.append((start, end))
    return found, student


def _months_covered(intervals: list[tuple[int, int]]) -> int:
    total, last_end = 0, 0
    for start, end in sorted(intervals):
        start = max(start, last_end)
        if end > start:
            total += end - start
            last_end = end
    return total


def user_years(request: SearchRequest, today: date | None = None) -> int | None:
    """Years of work experience the background shows (see the module docstring), or None.
    `today` is injectable for tests."""
    text = request.background
    stated = [int(n) for n in _YEARS.findall(text) if int(n) <= 40]
    intervals, student = _work_intervals(text, today or date.today())
    if stated or intervals:
        return max([*stated, _months_covered(intervals) // 12])
    return 0 if student or _NEW_GRAD.search(text) else None
