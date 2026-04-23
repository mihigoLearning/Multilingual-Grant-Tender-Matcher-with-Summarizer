#!/usr/bin/env python3
"""
matcher.py — T2.2 CLI entry point.

Usage:
    python matcher.py --profile 02 --topk 5            # rank + print
    python matcher.py --profile 02 --write-summaries   # also write .md files
    python matcher.py --all --write-summaries          # process every profile
    python matcher.py --eval                           # run offline evaluation

The hot path is `rank(profile)` — a pure function that returns ranked
(tender_id, score, components) tuples for a given profile dict.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from parser import parse_directory  # noqa: E402
from ranker import Matcher, MatchScore  # noqa: E402
from summarizer import summarize  # noqa: E402


# --- Public API (named in the brief: matcher.py::rank) -----------------------

def rank(profile: dict, topk: int = 5, matcher: Matcher | None = None) -> list[MatchScore]:
    """
    Rank tenders for a single profile.

    The score is a weighted sum of six signals:
      - BM25 over (title + body)             — primary lexical retrieval
      - char-ngram TF-IDF cosine             — cross-lingual fallback
      - sector match (1.0 / 0.0)             — structured hard signal
      - budget fit vs. past_funding          — size compatibility
      - deadline fit vs. today (30-180 days) — realism
      - language fit (primary / secondary)   — publication language bonus

    Language detection happens once per tender at parse time; budget fit uses
    past_funding as an anchor; deadline fit decays outside the 30-180 day
    application window. All CPU-only, no models downloaded.
    """
    if matcher is None:
        tenders = parse_directory(ROOT / "tenders")
        matcher = Matcher(tenders)
    return matcher.rank(profile, topk=topk)


# --- Helpers -----------------------------------------------------------------

def _load_profiles() -> list[dict]:
    return json.loads((ROOT / "data" / "profiles.json").read_text(encoding="utf-8"))


def _get_profile(pid: str, profiles: list[dict]) -> dict:
    # Accept "02" or "P02"
    key = pid if pid.startswith("P") else f"P{int(pid):02d}"
    for p in profiles:
        if p["id"] == key:
            return p
    raise SystemExit(f"Profile {key} not found. Available: {[p['id'] for p in profiles]}")


def _print_ranked(profile: dict, ranked: list[MatchScore]) -> None:
    print(f"\nProfile {profile['id']}  [sector={profile['sector']}  "
          f"country={profile['country']}  lang={profile['languages'][0]}]")
    print(f"Needs: {profile['needs_text'][:90]}{'…' if len(profile['needs_text']) > 90 else ''}\n")
    print(f"{'Rank':<5}{'Tender':<7}{'Score':<8}{'Sector':<12}{'Budget':<10}{'Deadline':<13}{'Lang':<5}Title")
    print("-" * 100)
    for i, m in enumerate(ranked, 1):
        t = m.tender
        budget = f"${t.budget//1000}k" if t.budget and t.budget < 1_000_000 else (
            f"${t.budget//1_000_000}M" if t.budget else "?")
        print(f"{i:<5}{t.id:<7}{m.score:<8.3f}{(t.sector or '?'):<12}"
              f"{budget:<10}{(t.deadline or '?'):<13}{t.lang:<5}{t.title[:40]}")


def _write_summaries(profile: dict, ranked: list[MatchScore]) -> list[Path]:
    out_dir = ROOT / "summaries"
    out_dir.mkdir(exist_ok=True)
    written = []
    for m in ranked:
        fname = f"{profile['id']}_{m.tender_id}.md"
        path = out_dir / fname
        header = (f"<!-- profile={profile['id']} tender={m.tender_id} "
                  f"score={m.score:.3f} bm25={m.components['bm25']:.3f} "
                  f"tfidf={m.components['tfidf']:.3f} -->\n\n")
        path.write_text(header + summarize(m.tender, profile, m) + "\n", encoding="utf-8")
        written.append(path)
    return written


# --- CLI ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Multilingual Grant & Tender Matcher")
    ap.add_argument("--profile", help="Profile id (e.g. 02 or P02)")
    ap.add_argument("--topk", type=int, default=5, help="Top-k tenders to return (default 5)")
    ap.add_argument("--all", action="store_true", help="Process every profile")
    ap.add_argument("--write-summaries", action="store_true",
                    help="Write .md summaries to summaries/")
    ap.add_argument("--eval", action="store_true",
                    help="Run offline evaluation (MRR@5, Recall@5)")
    args = ap.parse_args()

    if args.eval:
        from evaluate import evaluate, print_report
        print_report(evaluate(k=args.topk))
        return 0

    if not (args.profile or args.all):
        ap.print_help()
        return 1

    profiles = _load_profiles()
    tenders = parse_directory(ROOT / "tenders")
    matcher = Matcher(tenders)

    targets = profiles if args.all else [_get_profile(args.profile, profiles)]

    total_written = 0
    for p in targets:
        ranked = rank(p, topk=args.topk, matcher=matcher)
        _print_ranked(p, ranked)
        if args.write_summaries:
            written = _write_summaries(p, ranked)
            total_written += len(written)

    if args.write_summaries:
        print(f"\nWrote {total_written} summary file(s) to summaries/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
