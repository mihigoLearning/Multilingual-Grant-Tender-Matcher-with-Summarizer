"""
Hybrid ranker combining lexical retrieval (BM25) with cross-lingual character
n-gram TF-IDF, plus structured signals (sector, budget fit, deadline, language).

No embedding model downloads — everything runs on CPU in <1s for 40 tenders.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from parser import Tender


# --- Tokenisation ------------------------------------------------------------

STOPWORDS = {
    # English
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "we", "our", "is", "are", "be", "this", "that", "it", "as", "at", "from",
    # French
    "le", "la", "les", "de", "du", "des", "et", "ou", "pour", "dans", "sur",
    "avec", "par", "nous", "notre", "nos", "est", "sont", "un", "une", "ce",
    "cette", "ces", "il", "elle", "au", "aux", "à", "en",
}

TOKEN_RE = re.compile(r"[a-zàâäéèêëïîôöùûüç0-9']+", re.IGNORECASE | re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOPWORDS and len(t) > 1]


# --- Structured-signal scoring ----------------------------------------------

def budget_fit(tender_budget: int | None, past_funding: int) -> float:
    """
    Score [0,1]. A business with past_funding F is likely ready for ~5x that.
    Tenders within 0.5x-10x the target get full credit; outside falls off.
    """
    if tender_budget is None:
        return 0.3  # neutral
    target = max(past_funding * 5, 50_000)
    ratio = tender_budget / target
    if 0.5 <= ratio <= 10:
        return 1.0
    # Exponential falloff outside the window
    if ratio < 0.5:
        return max(0.0, ratio / 0.5)
    return max(0.0, 1.0 / math.log(ratio + 1))


def deadline_fit(deadline_iso: str | None, today: date | None = None) -> float:
    """
    Score [0,1]. Deadlines 30-180 days out are ideal; too-soon or too-far decays.
    """
    if deadline_iso is None:
        return 0.3
    today = today or date(2026, 4, 23)  # hackathon reference date
    try:
        d = date.fromisoformat(deadline_iso)
    except ValueError:
        return 0.3
    days = (d - today).days
    if days < 0:
        return 0.0  # already expired
    if 30 <= days <= 180:
        return 1.0
    if days < 30:
        return max(0.2, days / 30)
    return max(0.2, 180 / days)


def language_fit(tender_lang: str, profile_languages: list[str]) -> float:
    """Full credit if primary language matches; half if secondary; small baseline otherwise."""
    if not profile_languages:
        return 0.5
    if tender_lang == profile_languages[0]:
        return 1.0
    if tender_lang in profile_languages:
        return 0.6
    return 0.3


def sector_fit(tender_sector: str | None, profile_sector: str) -> float:
    if tender_sector is None:
        return 0.3
    return 1.0 if tender_sector == profile_sector else 0.0


# --- Index -------------------------------------------------------------------

@dataclass
class MatchScore:
    tender_id: str
    score: float
    components: dict  # for explainability in summaries
    tender: Tender


class Matcher:
    """
    Hybrid ranker. Build once per tender corpus, then call `rank(profile)`.
    """

    # Weights tuned for "simple but intelligent": lexical signal dominates,
    # structured signals refine the ranking.
    ## BM25 INDEXING AND SCORING
    W_BM25 = 0.35 # Dominant signal for relevance; fast and effective lexical retrieval.
    
    # TF-IDF COSINE SIMILARITY OVER CHARACTER N-GRAMS
    W_TFIDF = 0.25 # cross-lingual fallback; captures shared roots like "agri", "fin", "tech", "solar/solaire".
    
    
    W_SECTOR = 0.20 # Hard filter: sector match is a strong signal of relevance (1.0 vs 0.0).
    # The ranking refinement layer. 0.2
    W_BUDGET = 0.08
    W_DEADLINE = 0.07
    W_LANG = 0.05

    def __init__(self, tenders: list[Tender]):
        self.tenders = tenders
        self._build_index()

    def _build_index(self) -> None:
        # Corpus for lexical retrieval: title + body (we reuse `text` which has both).
        self._tokenized_corpus = [tokenize(t.text) for t in self.tenders]
        self._bm25 = BM25Okapi(self._tokenized_corpus)

        # Character n-gram TF-IDF gives cross-lingual robustness: shared
        # Latin roots like "agri", "fin", "tech", "solar/solaire" produce
        # overlapping n-grams even across EN/FR.
        self._tfidf = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
        )
        corpus_strs = [t.text for t in self.tenders]
        self._tfidf_matrix = self._tfidf.fit_transform(corpus_strs)

    # -- scoring --------------------------------------------------------------

    def _bm25_scores(self, query: str) -> np.ndarray:
        tokens = tokenize(query)
        if not tokens:
            return np.zeros(len(self.tenders))
        raw = np.asarray(self._bm25.get_scores(tokens))
        # Normalize to [0,1] per query (max-scaling; simple and stable)
        m = raw.max()
        return raw / m if m > 0 else raw

    def _tfidf_scores(self, query: str) -> np.ndarray:
        q = self._tfidf.transform([query])
        sims = cosine_similarity(q, self._tfidf_matrix).ravel()
        m = sims.max()
        return sims / m if m > 0 else sims

    def rank(self, profile: dict, topk: int = 5) -> list[MatchScore]:
        """
        Rank tenders for a profile. Returns top-k MatchScore objects.

        The query concatenates the sector keyword, profile country, and the
        free-text needs — letting the lexical retriever pick up on domain terms
        while the structured signals (budget/deadline/sector) refine the order.
        """
        query = f"{profile['sector']} {profile['country']} {profile['needs_text']}"

        bm25_s = self._bm25_scores(query)
        tfidf_s = self._tfidf_scores(query)

        scored: list[MatchScore] = []
        for i, t in enumerate(self.tenders):
            comps = {
                "bm25": float(bm25_s[i]),
                "tfidf": float(tfidf_s[i]),
                "sector": sector_fit(t.sector, profile["sector"]),
                "budget": budget_fit(t.budget, profile.get("past_funding", 0)),
                "deadline": deadline_fit(t.deadline),
                "language": language_fit(t.lang, profile.get("languages", [])),
            }
            score = (
                self.W_BM25 * comps["bm25"] +
                self.W_TFIDF * comps["tfidf"] +
                self.W_SECTOR * comps["sector"] +
                self.W_BUDGET * comps["budget"] +
                self.W_DEADLINE * comps["deadline"] +
                self.W_LANG * comps["language"]
            )
            scored.append(MatchScore(tender_id=t.id, score=score, components=comps, tender=t))

        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:topk]


if __name__ == "__main__":
    import json
    from parser import parse_directory
    root = Path(__file__).resolve().parent.parent
    tenders = parse_directory(root / "tenders")
    profiles = json.loads((root / "data" / "profiles.json").read_text(encoding="utf-8"))

    matcher = Matcher(tenders)
    p = profiles[1]  # profile 02
    print(f"Profile {p['id']}  sector={p['sector']}  country={p['country']}  lang={p['languages']}")
    print(f"Needs: {p['needs_text'][:80]}...\n")
    for rank, m in enumerate(matcher.rank(p, topk=5), 1):
        t = m.tender
        print(f"  {rank}. {t.id}  score={m.score:.3f}  "
              f"sector={t.sector}  budget={t.budget}  lang={t.lang}  "
              f"[bm25={m.components['bm25']:.2f} tfidf={m.components['tfidf']:.2f}]")
