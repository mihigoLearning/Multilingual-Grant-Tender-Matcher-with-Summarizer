"""Tests for src/evaluate.py — metric correctness + end-to-end sanity on real data."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from evaluate import reciprocal_rank, recall, load_gold, evaluate  # noqa: E402


class TestReciprocalRank(unittest.TestCase):
    def test_hit_at_rank_one(self):
        self.assertEqual(reciprocal_rank(["A", "B", "C"], {"A"}), 1.0)

    def test_hit_at_rank_three(self):
        self.assertAlmostEqual(reciprocal_rank(["X", "Y", "A"], {"A"}), 1 / 3)

    def test_no_hit(self):
        self.assertEqual(reciprocal_rank(["X", "Y", "Z"], {"A"}), 0.0)

    def test_first_relevant_counts(self):
        # Even though two are relevant, only the first hit matters for RR
        self.assertEqual(reciprocal_rank(["X", "A", "B"], {"A", "B"}), 0.5)


class TestRecall(unittest.TestCase):
    def test_all_found(self):
        self.assertEqual(recall(["A", "B", "C"], {"A", "B", "C"}), 1.0)

    def test_partial(self):
        self.assertAlmostEqual(recall(["A", "X"], {"A", "B", "C"}), 1 / 3)

    def test_no_relevant(self):
        self.assertEqual(recall(["A"], set()), 0.0)

    def test_extras_dont_help(self):
        # Hits outside the relevant set don't inflate recall
        self.assertAlmostEqual(recall(["A", "Z", "Y"], {"A", "B"}), 0.5)


class TestLoadGold(unittest.TestCase):
    def test_parses_gold_csv(self):
        gold_path = ROOT / "data" / "gold_matches.csv"
        if not gold_path.exists():
            self.skipTest("run `python src/generate_data.py` first")
        gold = load_gold(gold_path)
        self.assertEqual(len(gold), 10)
        for pid, tenders in gold.items():
            self.assertEqual(len(tenders), 3)  # exactly 3 per profile
            self.assertTrue(all(t.startswith("T") for t in tenders))


class TestEndToEndEval(unittest.TestCase):
    """The headline number — guards against regression."""

    def test_metrics_meet_baseline(self):
        tenders_dir = ROOT / "tenders"
        if not any(tenders_dir.iterdir()):
            self.skipTest("run `python src/generate_data.py` first")
        results = evaluate(k=5)
        self.assertEqual(results["n_profiles"], 10)
        self.assertEqual(results["n_tenders"], 40)
        # Baseline we validated during development was 0.933 for both.
        # Guard against regressions below 0.85 (still strong, gives retuning room).
        self.assertGreaterEqual(results["mrr_at_k"], 0.85)
        self.assertGreaterEqual(results["recall_at_k"], 0.85)
        # 3-minute budget sanity
        self.assertLess(results["total_end_to_end_ms"], 3 * 60 * 1000)

    def test_three_confusion_cases_returned(self):
        tenders_dir = ROOT / "tenders"
        if not any(tenders_dir.iterdir()):
            self.skipTest("run `python src/generate_data.py` first")
        results = evaluate(k=5)
        self.assertEqual(len(results["confusion_cases"]), 3)


if __name__ == "__main__":
    unittest.main()
