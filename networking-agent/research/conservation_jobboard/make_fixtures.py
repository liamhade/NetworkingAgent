"""Throwaway: trim saved pages in out/ into offline test fixtures.

Keeps only ``div#search_results_container`` and strips
Livewire state (wire:* attributes with checksums/ids), scripts, forms and CSRF tokens.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Comment

OUT = Path(__file__).parent / "out"
FIXTURES = Path(__file__).parents[2] / "backend" / "tests" / "conservation_jobboard" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)


def trim(src: str, dest: str, max_main: int | None = None) -> None:
    soup = BeautifulSoup((OUT / src).read_text(encoding="utf-8"), "html.parser")
    container = soup.select_one("#search_results_container")
    for tag in container.find_all(["script", "style", "form", "noscript", "svg", "iframe", "img"]):
        tag.decompose()
    for c in container.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in [container, *container.find_all(True)]:
        for attr in list(tag.attrs):
            if attr.startswith("wire:") or attr.startswith("x-") or attr == "style":
                del tag.attrs[attr]
    if max_main is not None:
        main = [
            a.find_parent("div", class_="listing__job").parent
            for a in container.select('a.gtag-job-link[list_name="main-results-page"]')
        ]
        for wrapper in main[max_main:]:
            wrapper.decompose()
    html = f"<!DOCTYPE html>\n<html><body>\n{container}\n</body></html>\n"
    html = re.sub(r"\n\s*\n+", "\n", html)
    (FIXTURES / dest).write_text(html, encoding="utf-8")
    print(dest, len(html))


if __name__ == "__main__":
    trim("search.html", "search_page1.html", max_main=int(sys.argv[1]) if len(sys.argv) > 1 else 4)
    trim("search_p2.html", "search_page2.html", max_main=3)
    trim("search_empty.html", "search_empty.html")
