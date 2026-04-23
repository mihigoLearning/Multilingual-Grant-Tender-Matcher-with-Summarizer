"""Tests for src/ranker.py — structured signals and end-to-end ranking."""

import sys
import time
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from parser import Tender, parse_directory  # noqa: E402
from ranker import (  # noqa: E402
    tokenize, budget_fit, deadline_fit, language_fit, sector_fit, Matcher,
)


class TestTokenize(unittest.TestCase):
    def test_removes_stopwords_and_lowercases(self):
        toks = tokenize("We are the cleantech company in Kenya.")
        self.assertNotIn("the", toks)
        self.assertNotIn("we", toks)
        self.assertIn("cleantech", toks)
        self.assertIn("kenya", toks)

    def test_handles_french_accents(self):
        toks = tokenize("Appel à propositions pour énergie solaire")
        self.assertIn("appel", toks)
        self.assertIn("propositions", toks)
        self.assertIn("énergie", toks)
        self.assertNotIn("à", toks)  # stopword


class TestSectorFit(unittest.TestCase):
    def test_match_gets_full_credit(self):
        self.assertEqual(sector_fit("agritech", "agritech"), 1.0)

    def test_mismatch_gets_zero(self):
        self.assertEqual(sector_fit("fintech", "agritech"), 0.0)

    def test_missing_gets_neutral(self):
        self.assertEqual(sector_fit(None, "agritech"), 0.3)


class TestBudgetFit(unittest.TestCase):
    def test_in_window_gets_full_credit(self):
        # past_funding=50k → target=250k → 200k is in [125k, 2.5M] window
        self.assertEqual(budget_fit(200_000, 50_000), 1.0)

    def test_too_small_decays(self):
        # past_funding=100k → target=500k; 5k is tiny
        score = budget_fit(5_000, 100_000)
        self.assertLess(score, 0.5)

    def test_too_large_decays(self):
        # past_funding=0 → target=50k; 1M is 20x target
        score = budget_fit(1_000_000, 0)
        self.assertLess(score, 0.5)

    def test_missing_budget_neutral(self):
        self.assertEqual(budget_fit(None, 50_000), 0.3)


class TestDeadlineFit(unittest.TestCase):
    REF = date(2026, 4, 23)  # matches resolver.py's reference date

    def test_ideal_window(self):
        self.assertEqual(deadline_fit("2026-06-15", today=self.REF), 1.0)

    def test_expired_gets_zero(self):
        self.assertEqual(deadline_fit("2026-01-01", today=self.REF), 0.0)

    def test_too_close_decays(self):
        # 10 days out
        self.assertLess(deadline_fit("2026-05-03", today=self.REF), 1.0)

    def test_too_far_decays(self):
        # 350 days out
        self.assertLess(deadline_fit("2027-04-08", today=self.REF), 1.0)

    def test_missing_neutral(self):
        self.assertEqual(deadline_fit(None), 0.3)


class TestLanguageFit(unittest.TestCase):
    def test_primary_match(self):
        self.assertEqual(language_fit("fr", ["fr", "en"]), 1.0)

    def test_secondary_match(self):
        self.assertEqual(language_fit("en", ["fr", "en"]), 0.6)

    def test_no_match(self):
        self.assertEqual(language_fit("fr", ["en"]), 0.3)


def _mk_tender(tid: str, lang: str, sector: str, budget: int,
               deadline: str, body: str) -> Tender:
    return Tender(
        id=tid, path=f"/tmp/{tid}", format="txt", lang=lang,
        title=f"Title {tid}", sector=sector, budget=budget,
        deadline=deadline, region="East Africa",
        text=f"TITLE: Title {tid}\n{body}",
    )


class TestMatcherRanking(unittest.TestCase):
    """End-to-end ranking on a small hand-crafted corpus."""

    def setUp(self):
        self.tenders = [
            _mk_tender("A", "fr", "cleantech", 200_000, "2026-06-15",
                       "énergie solaire panneaux installation hors réseau"),
            _mk_tender("B", "en", "cleantech", 200_000, "2026-06-15",
                       "solar home systems off-grid installation"),
            _mk_tender("C", "en", "fintech", 50_000, "2026-06-15",
                       "mobile lending credit scoring informal traders"),
            _mk_tender("D", "fr", "agritech", 50_000, "2026-06-15",
                       "agriculture conseil mobile petits exploitants"),
        ]
        self.matcher = Matcher(self.tenders)

    def test_sector_is_primary_signal(self):
        profile = {
            "id": "P01", "sector": "fintech", "country": "Kenya",
            "employees": 10, "languages": ["en"], "past_funding": 10_000,
            "needs_text": "mobile lending for informal traders",
        }
        ranked = self.matcher.rank(profile, topk=4)
        self.assertEqual(ranked[0].tender.id, "C")  # fintech wins

    def test_language_preference_breaks_ties(self):
        # Both A and B are cleantech with identical structure — language fit
        # and BM25 on French vocabulary should tip French profile toward A.
        profile = {
            "id": "P02", "sector": "cleantech", "country": "DRC",
            "employees": 15, "languages": ["fr", "en"], "past_funding": 10_000,
            "needs_text": "énergie solaire hors réseau installation",
        }
        ranked = self.matcher.rank(profile, topk=2)
        self.assertEqual(ranked[0].tender.id, "A")
        self.assertEqual(ranked[0].tender.lang, "fr")

    def test_score_components_are_present(self):
        profile = {
            "id": "P03", "sector": "cleantech", "country": "Kenya",
            "employees": 10, "languages": ["en"], "past_funding": 50_000,
            "needs_text": "solar home systems",
        }
        m = self.matcher.rank(profile, topk=1)[0]
        for key in ("bm25", "tfidf", "sector", "budget", "deadline", "language"):
            self.assertIn(key, m.components)
            self.assertGreaterEqual(m.components[key], 0.0)
            self.assertLessEqual(m.components[key], 1.0)

    def test_topk_respected(self):
        profile = {
            "id": "P04", "sector": "cleantech", "country": "Kenya",
            "employees": 10, "languages": ["en"], "past_funding": 0,
            "needs_text": "solar",
        }
        self.assertEqual(len(self.matcher.rank(profile, topk=2)), 2)
        self.assertEqual(len(self.matcher.rank(profile, topk=4)), 4)


class TestMatcherPerformance(unittest.TestCase):
    """Validate the <3 min budget the brief specifies."""

    def test_full_corpus_ranks_fast(self):
        tenders_dir = ROOT / "tenders"
        if not any(tenders_dir.iterdir()):
            self.skipTest("run `python src/generate_data.py` first")
        tenders = parse_directory(tenders_dir)
        matcher = Matcher(tenders)
        profile = {
            "id": "P01", "sector": "cleantech", "country": "Kenya",
            "employees": 10, "languages": ["en"], "past_funding": 50_000,
            "needs_text": "solar home systems off-grid",
        }
        # 10 profiles' worth of ranking calls should comfortably fit in 1s
        t0 = time.perf_counter()
        for _ in range(10):
            matcher.rank(profile, topk=5)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 1.0, f"10 rank calls took {elapsed:.3f}s — too slow")


if __name__ == "__main__":
    unittest.main()
