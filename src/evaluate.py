"""
Offline evaluation: MRR@5 and Recall@5 against data/gold_matches.csv.
Also reports the 3 most egregious confusion cases (largest rank drops
between the top-ranked tender and the lowest-ranked gold item).
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from parser import parse_directory
from ranker import Matcher


def load_gold(path: Path) -> dict[str, list[str]]:
    """Return {profile_id: [tender_id, tender_id, tender_id] ordered by rank}."""
    gold: dict[str, list[tuple[str, int]]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            gold[row["profile_id"]].append((row["tender_id"], int(row["rank"])))
    return {pid: [t for t, _ in sorted(v, key=lambda x: x[1])]
            for pid, v in gold.items()}


def reciprocal_rank(predicted: list[str], relevant: set[str]) -> float:
    for i, tid in enumerate(predicted, 1):
        if tid in relevant:
            return 1.0 / i
    return 0.0


def recall(predicted: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits = len(set(predicted) & relevant)
    return hits / len(relevant)


def evaluate(k: int = 5) -> dict:
    root = Path(__file__).resolve().parent.parent
    tenders = parse_directory(root / "tenders")
    profiles = json.loads((root / "data" / "profiles.json").read_text(encoding="utf-8"))
    gold = load_gold(root / "data" / "gold_matches.csv")

    t0 = time.perf_counter()
    matcher = Matcher(tenders)
    index_build_ms = (time.perf_counter() - t0) * 1000

    per_profile = []
    rr_total = 0.0
    recall_total = 0.0
    rank_times = []

    for p in profiles:
        t1 = time.perf_counter()
        ranked = matcher.rank(p, topk=k)
        rank_times.append((time.perf_counter() - t1) * 1000)
        predicted_ids = [m.tender_id for m in ranked]
        relevant = set(gold.get(p["id"], []))

        rr = reciprocal_rank(predicted_ids, relevant)
        rc = recall(predicted_ids, relevant)
        rr_total += rr
        recall_total += rc
        per_profile.append({
            "profile_id": p["id"],
            "sector": p["sector"],
            "country": p["country"],
            "primary_lang": p["languages"][0],
            "predicted": predicted_ids,
            "gold": gold.get(p["id"], []),
            "hits": sorted(set(predicted_ids) & relevant),
            "rr": rr,
            "recall": rc,
        })

    n = len(profiles)
    results = {
        "n_profiles": n,
        "n_tenders": len(tenders),
        "mrr_at_k": rr_total / n,
        "recall_at_k": recall_total / n,
        "k": k,
        "index_build_ms": round(index_build_ms, 1),
        "avg_rank_ms": round(sum(rank_times) / len(rank_times), 1),
        "total_end_to_end_ms": round(index_build_ms + sum(rank_times), 1),
        "per_profile": per_profile,
    }

    # Confusion cases: profiles where we hit the fewest gold items
    confusion = sorted(per_profile, key=lambda p: (p["recall"], p["rr"]))[:3]
    results["confusion_cases"] = confusion

    return results


def print_report(results: dict) -> None:
    print("=" * 72)
    print(f"Tenders: {results['n_tenders']}   Profiles: {results['n_profiles']}   k={results['k']}")
    print(f"MRR@{results['k']}:     {results['mrr_at_k']:.3f}")
    print(f"Recall@{results['k']}:  {results['recall_at_k']:.3f}")
    print(f"Index build: {results['index_build_ms']} ms   "
          f"Avg rank: {results['avg_rank_ms']} ms   "
          f"Total: {results['total_end_to_end_ms']} ms")
    print("=" * 72)
    print("\nPer-profile results:")
    print(f"  {'Profile':<7} {'Sector':<12} {'Lang':<5} {'RR':>6} {'Recall':>7}  Hits")
    for p in results["per_profile"]:
        print(f"  {p['profile_id']:<7} {p['sector']:<12} {p['primary_lang']:<5} "
              f"{p['rr']:>6.3f} {p['recall']:>7.3f}  {','.join(p['hits']) or '(none)'}")

    print("\n3 confusion cases (lowest recall first):")
    for p in results["confusion_cases"]:
        print(f"  {p['profile_id']} ({p['sector']}/{p['primary_lang']}): "
              f"predicted={p['predicted']}  gold={p['gold']}  hits={p['hits']}")


if __name__ == "__main__":
    results = evaluate(k=5)
    print_report(results)
    # Write machine-readable output for the notebook
    out = Path(__file__).resolve().parent.parent / "data" / "eval_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out}")
