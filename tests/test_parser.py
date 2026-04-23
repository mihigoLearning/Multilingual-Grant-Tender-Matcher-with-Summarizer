"""Tests for src/parser.py — field extraction, language detection, format handling."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from parser import (  # noqa: E402
    detect_language, parse_budget, parse_deadline, parse_sector,
    parse_title, parse_region, parse_file, parse_directory, read_text,
)


class TestFieldExtractors(unittest.TestCase):
    def test_budget_k_and_m(self):
        self.assertEqual(parse_budget("Total funding is 50k USD."), 50_000)
        self.assertEqual(parse_budget("The grant amount is 1M USD"), 1_000_000)
        self.assertEqual(parse_budget("Budget: 200K USD"), 200_000)
        self.assertEqual(parse_budget("Budget: 5k USD"), 5_000)

    def test_budget_picks_largest(self):
        # When multiple figures appear (e.g. "up to 1M USD, minimum 50k USD")
        self.assertEqual(parse_budget("range 50k USD to 1M USD"), 1_000_000)

    def test_budget_missing(self):
        self.assertIsNone(parse_budget("No dollar figure anywhere"))

    def test_deadline(self):
        self.assertEqual(parse_deadline("deadline 2026-06-15 applies"), "2026-06-15")
        self.assertIsNone(parse_deadline("no date here"))

    def test_sector_case_insensitive(self):
        self.assertEqual(parse_sector("We support Agritech innovation"), "agritech")
        self.assertEqual(parse_sector("HEALTHTECH focus"), "healthtech")
        self.assertIsNone(parse_sector("generic boilerplate text"))

    def test_region_en_and_fr(self):
        self.assertEqual(parse_region("focused on East Africa region"), "East Africa")
        self.assertEqual(parse_region("opérations en Afrique de l'Ouest"), "Afrique de l'Ouest")

    def test_title_from_title_line(self):
        text = "TITLE: My Important Call\nSECTOR: agritech\n..."
        self.assertEqual(parse_title(text, "en"), "My Important Call")

    def test_title_fallback_first_nontrivial_line(self):
        text = "   \n\nA meaningful first line of text\nsecond line"
        self.assertEqual(parse_title(text, "en"), "A meaningful first line of text")


class TestLanguageDetect(unittest.TestCase):
    def test_english(self):
        self.assertEqual(detect_language(
            "This call for proposals invites eligible applicants to submit."
        ), "en")

    def test_french(self):
        self.assertEqual(detect_language(
            "Cet appel à propositions invite les candidats éligibles à soumettre."
        ), "fr")

    def test_defaults_to_english_on_gibberish(self):
        # Short or ambiguous input — must still return a valid code
        result = detect_language("")
        self.assertIn(result, ("en", "fr"))


class TestReadText(unittest.TestCase):
    def test_txt_and_html_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.txt").write_text("hello txt body", encoding="utf-8")
            (tmp / "b.html").write_text(
                "<html><body><h1>hi</h1><p>body</p></body></html>", encoding="utf-8")
            self.assertIn("hello txt body", read_text(tmp / "a.txt"))
            html_text = read_text(tmp / "b.html")
            self.assertIn("hi", html_text)
            self.assertIn("body", html_text)
            with self.assertRaises(ValueError):
                read_text(tmp / "c.docx")


class TestParseDirectoryIntegration(unittest.TestCase):
    """Smoke test on the real tenders/ folder (after generate_data.py ran)."""

    def test_parses_all_40_with_no_missing_core_fields(self):
        tenders_dir = ROOT / "tenders"
        if not any(tenders_dir.iterdir()):
            self.skipTest("run `python src/generate_data.py` first")
        tenders = parse_directory(tenders_dir)
        self.assertEqual(len(tenders), 40)
        # Every tender has language, sector, budget, deadline
        self.assertTrue(all(t.lang in ("en", "fr") for t in tenders))
        self.assertTrue(all(t.sector is not None for t in tenders))
        self.assertTrue(all(t.budget is not None for t in tenders))
        self.assertTrue(all(t.deadline is not None for t in tenders))
        # Format diversity — we generate all three
        formats = {t.format for t in tenders}
        self.assertEqual(formats, {"txt", "html", "pdf"})


if __name__ == "__main__":
    unittest.main()
