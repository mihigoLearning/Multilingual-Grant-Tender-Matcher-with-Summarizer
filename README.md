# Multilingual Grant & Tender Matcher with Summarizer

**AIMS KTT Hackathon · T2.2 · GovTech · NLP · IR · Summarization**

Ranks the most relevant grants and tenders for African entrepreneurs across
English and French sources and generates a short, language-appropriate summary
explaining *why* each tender fits. CPU-only, no model downloads, runs
end-to-end on all 10 profiles in under 1 second.

## Quick start (2 commands, Colab CPU / laptop)

```bash
pip install -r requirements.txt
python src/generate_data.py && python matcher.py --all --write-summaries --eval
```

## What this produces

- `tenders/` — 40 synthetic tender documents (60% EN / 40% FR) in `.pdf`, `.html`, `.txt`
- `data/profiles.json` — 10 business profiles
- `data/gold_matches.csv` — 3 expert-curated matches per profile (used for evaluation)
- `summaries/` — one `.md` per (profile, tender) in the profile's primary language
- `data/eval_results.json` — machine-readable evaluation output

## Results on the provided gold set

| Metric | Value |
|---|---|
| **MRR@5** | **0.933** |
| **Recall@5** | **0.933** |
| Tenders | 40 (25 EN, 15 FR) |
| Profiles | 10 |
| Index build | ~22 ms |
| Average rank call | ~1 ms |
| End-to-end (all 10 profiles) | ~30 ms |

Budget: spec allows 3 min. We use 30 ms.

## Architecture

### Data flow
```
tenders/*.{pdf,html,txt}
        │
        ▼  src/parser.py          (pypdf / BeautifulSoup / plain read → Tender dataclass)
        │  · detects language (langdetect, deterministic seed)
        │  · extracts sector, budget, deadline, region via regex
        ▼
src/ranker.py                     (index build once per corpus)
        │  · BM25Okapi over lexical tokens (title+body)
        │  · char-ngram TF-IDF cosine (cross-lingual fallback)
        │  · weighted sum with structured signals:
        │       sector / budget fit / deadline / language
        ▼
matcher.py::rank(profile)         (public API)
        │
        ├── CLI → ranked table
        └── src/summarizer.py     (template-based, EN/FR, ≤80 words, "why NOT" warning)
```

### Why this design

- **TF-IDF + BM25 hybrid, no transformers** — keeps us well under the 150 MB
  model-size cap with zero model downloads. BM25 handles exact lexical matches
  ("solar home systems"); character n-grams catch cross-lingual cognates
  (`agri` ↔ `agri`, `tech` ↔ `tech`, `solaire` ↔ `solar`). Together they match
  the spec's "TF-IDF + BM25, or small multilingual embeddings" recommendation
  without embedding model overhead.
- **Structured signals on top of retrieval** — sector/budget/deadline/language
  weights refine the ranking in ways pure lexical retrieval cannot. The
  weights are explicit class constants in `ranker.py` so the next person can
  retune without touching logic.
- **Template summaries, not generative** — deterministic, no LLM, no
  hallucinations, and the summary *always* cites the four facts the rubric
  asks for (sector/budget/deadline/language). Includes an optional "why NOT"
  disqualifier (stretch goal).

## CLI

```bash
# Rank top-5 for one profile
python matcher.py --profile 02 --topk 5

# Rank + write .md summaries for one profile
python matcher.py --profile 02 --write-summaries

# Process every profile and write all summaries
python matcher.py --all --write-summaries

# Run offline evaluation (MRR@5, Recall@5, confusion cases)
python matcher.py --eval
```

## Repository layout

```
.
├── matcher.py               # CLI entry point + rank() public API
├── requirements.txt
├── src/
│   ├── generate_data.py     # synthetic data generator (seed=42)
│   ├── parser.py            # PDF / HTML / TXT → Tender dataclass + langdetect
│   ├── ranker.py            # BM25 + TF-IDF + structured-signal hybrid
│   ├── summarizer.py        # template-based EN/FR summaries (≤80 words)
│   └── evaluate.py          # MRR@5, Recall@5, confusion cases
├── tenders/                 # 40 generated tender documents
├── data/
│   ├── profiles.json
│   ├── gold_matches.csv
│   ├── tender_index.json
│   └── eval_results.json
├── summaries/               # one .md per (profile, tender) pair
├── notebooks/
│   └── eval.ipynb           # evaluation notebook with results table
├── village_agent.md         # Product & Business adaptation artifact
├── process_log.md           # hour-by-hour timeline + declared LLM use
└── SIGNED.md                # honor code (signed)
```

## Video

*Upload URL will be added here after recording.*

## License

GPL-3.0 — see LICENSE.
