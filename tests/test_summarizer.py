"""Tests for src/summarizer.py — language routing, word cap, why-NOT logic."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from parser import Tender  # noqa: E402
from ranker import MatchScore  # noqa: E402
from summarizer import (  # noqa: E402
    summarize, summarize_en, summarize_fr, _truncate_words, _why_not,
    _fmt_budget_en, _fmt_budget_fr,
)


def _tender(**over) -> Tender:
    base = dict(
        id="T999", path="/tmp/T999.txt", format="txt", lang="en",
        title="Test Tender", sector="cleantech", budget=200_000,
        deadline="2026-06-15", region="East Africa", text="body",
    )
    base.update(over)
    return Tender(**base)


def _match(tender: Tender, **comps) -> MatchScore:
    defaults = {"bm25": 0.8, "tfidf": 0.7, "sector": 1.0,
                "budget": 1.0, "deadline": 1.0, "language": 1.0}
    defaults.update(comps)
    return MatchScore(tender_id=tender.id, score=0.9,
                      components=defaults, tender=tender)


def _profile(**over) -> dict:
    base = {"id": "P99", "sector": "cleantech", "country": "Kenya",
            "employees": 10, "languages": ["en"], "past_funding": 50_000,
            "needs_text": "solar home systems for off-grid households"}
    base.update(over)
    return base


class TestBudgetFormatters(unittest.TestCase):
    def test_en(self):
        self.assertEqual(_fmt_budget_en(50_000), "USD 50k")
        self.assertEqual(_fmt_budget_en(1_000_000), "USD 1M")
        self.assertEqual(_fmt_budget_en(None), "unspecified budget")

    def test_fr(self):
        self.assertEqual(_fmt_budget_fr(200_000), "200 k USD")
        self.assertEqual(_fmt_budget_fr(1_000_000), "1 M USD")
        self.assertEqual(_fmt_budget_fr(None), "budget non spécifié")


class TestTruncateWords(unittest.TestCase):
    def test_under_cap_unchanged(self):
        self.assertEqual(_truncate_words("one two three", 80), "one two three")

    def test_over_cap_truncates_with_ellipsis(self):
        long = " ".join(f"w{i}" for i in range(100))
        out = _truncate_words(long, 80)
        self.assertTrue(out.endswith("…"))
        # Content before ellipsis should be 80 tokens
        self.assertEqual(len(out.rstrip("…").split()), 80)


class TestLanguageRouting(unittest.TestCase):
    def test_french_profile_gets_french_summary(self):
        p = _profile(languages=["fr", "en"])
        t = _tender()
        m = _match(t)
        out = summarize(t, p, m)
        self.assertIn("Cet appel correspond", out)
        self.assertNotIn("This tender matches", out)

    def test_english_profile_gets_english_summary(self):
        p = _profile(languages=["en"])
        t = _tender()
        m = _match(t)
        out = summarize(t, p, m)
        self.assertIn("This tender matches", out)


class TestSummaryContentFacts(unittest.TestCase):
    """Rubric requires the summary to cite sector, budget fit, and deadline."""

    def test_english_cites_all_three(self):
        p = _profile()
        t = _tender(sector="cleantech", budget=200_000, deadline="2026-06-15")
        m = _match(t)
        out = summarize_en(t, p, m)
        self.assertIn("cleantech", out)
        self.assertIn("USD 200k", out)
        # Deadline verdict is derived, not printed raw — check for "deadline" word
        self.assertIn("deadline", out.lower())

    def test_french_cites_all_three(self):
        p = _profile(languages=["fr"])
        t = _tender(sector="agritech", budget=1_000_000, deadline="2026-06-15", lang="fr")
        m = _match(t, budget=0.6)
        out = summarize_fr(t, p, m)
        self.assertIn("agritech", out)
        self.assertIn("1 M USD", out)
        self.assertIn("échéance", out)


class TestWhyNot(unittest.TestCase):
    def test_expired_deadline_flagged_en(self):
        t = _tender(deadline="2026-01-01")
        p = _profile()
        m = _match(t, deadline=0.0)
        msg = _why_not(t, p, m.components, "en")
        self.assertIsNotNone(msg)
        self.assertIn("deadline", msg.lower())

    def test_expired_deadline_flagged_fr(self):
        t = _tender(deadline="2026-01-01")
        p = _profile(languages=["fr"])
        m = _match(t, deadline=0.0)
        msg = _why_not(t, p, m.components, "fr")
        self.assertIsNotNone(msg)
        self.assertIn("échéance", msg.lower())

    def test_sector_mismatch_flagged(self):
        t = _tender(sector="agritech")
        p = _profile(sector="cleantech")
        m = _match(t, sector=0.0)
        msg = _why_not(t, p, m.components, "en")
        self.assertIsNotNone(msg)
        self.assertIn("sector", msg.lower())

    def test_clean_match_returns_none(self):
        t = _tender()
        p = _profile()
        m = _match(t)  # all 1.0
        self.assertIsNone(_why_not(t, p, m.components, "en"))


class TestWordCap(unittest.TestCase):
    def test_paragraph_respects_80_word_cap(self):
        # Stress the summariser with a long needs_text
        long_need = "we do " + "solar energy distribution " * 50
        p = _profile(needs_text=long_need)
        t = _tender()
        m = _match(t)
        out = summarize_en(t, p, m)
        # The descriptive paragraph is line index 2
        paragraph = out.splitlines()[2]
        self.assertLessEqual(len(paragraph.split()), 82)  # 80 + possible "…"


if __name__ == "__main__":
    unittest.main()
