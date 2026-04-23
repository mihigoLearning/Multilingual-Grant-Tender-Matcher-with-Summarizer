"""
Document parser for tenders/.

Reads .pdf / .html / .txt, detects language (en/fr), and extracts structured
fields (title, sector, budget, deadline, region) using regex heuristics — no
LLM calls, deterministic, <50ms per doc on CPU.
"""

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from langdetect import DetectorFactory, detect
from pypdf import PdfReader

DetectorFactory.seed = 0  # deterministic langdetect

SECTORS = ["agritech", "healthtech", "cleantech", "edtech", "fintech", "wastetech"]

# Budget patterns: 5k USD, 50k USD, 200k USD, 1M USD
BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([kKmM])\s*USD", re.IGNORECASE)
# ISO date: 2026-04-15
DATE_RE = re.compile(r"\b(20\d{2}-[01]\d-[0-3]\d)\b")
# Title line "TITLE: ..." (txt) — fallback: first non-empty line
TITLE_LINE_RE = re.compile(r"^\s*TITLE\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Tender:
    id: str
    path: str
    format: str
    lang: str
    title: str
    sector: Optional[str]
    budget: Optional[int]
    deadline: Optional[str]
    region: Optional[str]
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def read_text(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "txt":
        return path.read_text(encoding="utf-8")
    if suffix == "html":
        html = path.read_text(encoding="utf-8")
        # get_text preserves labels separated by newlines — helps field extraction
        return BeautifulSoup(html, "html.parser").get_text("\n")
    if suffix == "pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise ValueError(f"Unsupported format: {path.suffix}")


def parse_budget(text: str) -> Optional[int]:
    """Return the largest budget figure mentioned, in USD."""
    candidates = []
    for m in BUDGET_RE.finditer(text):
        num = float(m.group(1))
        unit = m.group(2).lower()
        mult = 1_000 if unit == "k" else 1_000_000
        candidates.append(int(num * mult))
    return max(candidates) if candidates else None


def parse_deadline(text: str) -> Optional[str]:
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def parse_sector(text: str) -> Optional[str]:
    lower = text.lower()
    for s in SECTORS:
        if s in lower:
            return s
    return None


def parse_title(text: str, lang: str) -> str:
    m = TITLE_LINE_RE.search(text)
    if m:
        return m.group(1).strip()
    # Fallback: first non-trivial line
    for line in text.splitlines():
        s = line.strip()
        if len(s) > 10:
            return s[:140]
    return "(untitled)"


def parse_region(text: str) -> Optional[str]:
    # Simple fallback: scan for known region strings
    regions = [
        "East Africa", "West Africa", "Pan-African", "Sub-Saharan Africa",
        "Afrique de l'Est", "Afrique de l'Ouest", "Panafricain", "Afrique subsaharienne",
    ]
    for r in regions:
        if r.lower() in text.lower():
            return r
    return None


def detect_language(text: str) -> str:
    """Return 'en' or 'fr' — default 'en' on failure."""
    sample = text[:2000]
    try:
        code = detect(sample)
    except Exception:
        return "en"
    if code.startswith("fr"):
        return "fr"
    return "en"


def parse_file(path: Path) -> Tender:
    text = read_text(path)
    lang = detect_language(text)
    return Tender(
        id=path.stem,
        path=str(path),
        format=path.suffix.lstrip("."),
        lang=lang,
        title=parse_title(text, lang),
        sector=parse_sector(text),
        budget=parse_budget(text),
        deadline=parse_deadline(text),
        region=parse_region(text),
        text=text,
    )


def parse_directory(tenders_dir: Path) -> list[Tender]:
    paths = sorted(p for p in tenders_dir.iterdir()
                   if p.suffix.lower() in (".txt", ".html", ".pdf"))
    return [parse_file(p) for p in paths]


if __name__ == "__main__":
    import json, sys
    root = Path(__file__).resolve().parent.parent
    tenders = parse_directory(root / "tenders")
    print(f"Parsed {len(tenders)} tenders")
    langs = {"en": 0, "fr": 0}
    missing_sector = 0
    missing_budget = 0
    missing_deadline = 0
    for t in tenders:
        langs[t.lang] = langs.get(t.lang, 0) + 1
        if t.sector is None: missing_sector += 1
        if t.budget is None: missing_budget += 1
        if t.deadline is None: missing_deadline += 1
    print(f"Languages: {langs}")
    print(f"Missing: sector={missing_sector}  budget={missing_budget}  deadline={missing_deadline}")
    # Show one example
    print("\nExample:")
    ex = tenders[0]
    print(json.dumps({k: v for k, v in ex.to_dict().items() if k != "text"},
                     indent=2, ensure_ascii=False))
