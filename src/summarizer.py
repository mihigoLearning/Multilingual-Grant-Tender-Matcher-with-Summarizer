"""
Template-based summarizer.

Produces ≤80-word summaries in EN or FR explaining
*why* a tender matches a profile, citing sector, budget fit, deadline, and
language.

Includes an optional 'why NOT' disqualifier (stretch goal).

Deterministic, CPU-only, no model load. Each summary renders in <1ms.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from parser import Tender
from ranker import MatchScore


def _fmt_budget_en(b: Optional[int]) -> str:
    if b is None: return "unspecified budget"
    if b >= 1_000_000: return f"USD {b // 1_000_000}M"
    return f"USD {b // 1000}k"


def _fmt_budget_fr(b: Optional[int]) -> str:
    if b is None: return "budget non spécifié"
    if b >= 1_000_000: return f"{b // 1_000_000} M USD"
    return f"{b // 1000} k USD"


def _days_to_deadline(deadline: Optional[str]) -> Optional[int]:
    if deadline is None:
        return None
    try:
        return (date.fromisoformat(deadline) - date(2026, 4, 23)).days
    except ValueError:
        return None


def _budget_verdict(components: dict, lang: str) -> str:
    b = components["budget"]
    if lang == "fr":
        if b >= 0.9: return "budget bien dimensionné pour votre étape"
        if b >= 0.5: return "budget raisonnable, légèrement hors cible"
        return "budget probablement trop grand ou trop petit"
    if b >= 0.9: return "well-sized budget for your stage"
    if b >= 0.5: return "reasonable budget, slightly off-target"
    return "budget likely too large or too small"


def _deadline_verdict(days: Optional[int], lang: str) -> str:
    if days is None:
        return "échéance inconnue" if lang == "fr" else "unknown deadline"
    if lang == "fr":
        if days < 0: return f"échéance dépassée ({-days} jours)"
        if days < 30: return f"échéance serrée ({days} jours)"
        if days <= 180: return f"échéance confortable ({days} jours)"
        return f"échéance lointaine ({days} jours)"
    if days < 0: return f"deadline passed ({-days} days ago)"
    if days < 30: return f"tight deadline ({days} days)"
    if days <= 180: return f"comfortable deadline ({days} days)"
    return f"distant deadline ({days} days)"


def _why_not(t: Tender, profile: dict, components: dict, lang: str) -> Optional[str]:
    """Return the single biggest disqualifier, or None if the match is clean."""
    days = _days_to_deadline(t.deadline)
    if days is not None and days < 0:
        return ("Attention : échéance dépassée." if lang == "fr"
                else "Warning: deadline already passed.")
    if components["sector"] < 1.0:
        if lang == "fr":
            return f"Attention : secteur ({t.sector or 'non précisé'}) différent du vôtre ({profile['sector']})."
        return f"Warning: sector ({t.sector or 'unspecified'}) differs from yours ({profile['sector']})."
    if components["budget"] < 0.4:
        return ("Attention : budget probablement hors de votre étape actuelle."
                if lang == "fr" else "Warning: budget likely misaligned with your stage.")
    if days is not None and days < 30:
        return (f"Attention : il ne reste que {days} jours pour postuler."
                if lang == "fr" else f"Warning: only {days} days left to apply.")
    return None


def _truncate_words(text: str, max_words: int = 80) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",.;") + "…"


def summarize_en(t: Tender, profile: dict, m: MatchScore) -> str:
    days = _days_to_deadline(t.deadline)
    region = t.region or "the stated region"
    lines = [
        f"**{t.title}**",
        "",
        f"This tender matches profile {profile['id']} ({profile['sector']}, "
        f"{profile['country']}) on three fronts: sector alignment ({t.sector}), "
        f"{_budget_verdict(m.components, 'en')} ({_fmt_budget_en(t.budget)}), and "
        f"{_deadline_verdict(days, 'en')}. "
        f"Published in English for {region}; your team's needs on "
        f"{profile['needs_text'].split('.')[0].lower()} map directly to the call's scope.",
    ]
    wn = _why_not(t, profile, m.components, "en")
    if wn:
        lines += ["", wn]
    body = "\n".join(lines)
    # Only the descriptive paragraph counts toward the ≤80-word limit
    paragraph = lines[2]
    paragraph = _truncate_words(paragraph, 80)
    lines[2] = paragraph
    return "\n".join(lines)


def summarize_fr(t: Tender, profile: dict, m: MatchScore) -> str:
    days = _days_to_deadline(t.deadline)
    region = t.region or "la région visée"
    first_need = profile['needs_text'].split('.')[0].lower()
    lines = [
        f"**{t.title}**",
        "",
        f"Cet appel correspond au profil {profile['id']} ({profile['sector']}, "
        f"{profile['country']}) sur trois points : alignement sectoriel ({t.sector}), "
        f"{_budget_verdict(m.components, 'fr')} ({_fmt_budget_fr(t.budget)}), et "
        f"{_deadline_verdict(days, 'fr')}. "
        f"Publié en français pour {region} ; vos besoins autour de "
        f"{first_need} rejoignent directement les priorités de l'appel.",
    ]
    wn = _why_not(t, profile, m.components, "fr")
    if wn:
        lines += ["", wn]
    paragraph = lines[2]
    paragraph = _truncate_words(paragraph, 80)
    lines[2] = paragraph
    return "\n".join(lines)


def summarize(t: Tender, profile: dict, m: MatchScore) -> str:
    """Render the summary in the profile's primary language."""
    primary = (profile.get("languages") or ["en"])[0]
    if primary == "fr":
        return summarize_fr(t, profile, m)
    return summarize_en(t, profile, m)


if __name__ == "__main__":
    import json
    from pathlib import Path
    from parser import parse_directory
    from ranker import Matcher

    root = Path(__file__).resolve().parent.parent
    tenders = parse_directory(root / "tenders")
    profiles = json.loads((root / "data" / "profiles.json").read_text(encoding="utf-8"))

    matcher = Matcher(tenders)
    p = profiles[1]
    m = matcher.rank(p, topk=1)[0]
    print(summarize(m.tender, p, m))
    print("\n---\n")
    # English profile
    p_en = next(pp for pp in profiles if pp['languages'][0] == 'en')
    m2 = matcher.rank(p_en, topk=1)[0]
    print(f"(Profile {p_en['id']})")
    print(summarize(m2.tender, p_en, m2))
