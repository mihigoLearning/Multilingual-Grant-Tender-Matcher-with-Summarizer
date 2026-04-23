# Process Log — T2.2

**Candidate:** Munezero Mihigo Ribeus
**Challenge:** T2.2 — Multilingual Grant & Tender Matcher with Summarizer
**Start:** 2026-04-23 · 10:00 local

## Hour-by-hour timeline

### Hour 1 — Framing & data
- Read the brief end-to-end; wrote down the six scoring criteria as a
  checklist and pinned them on the monitor.
- Decided the architecture: **BM25 + char-ngram TF-IDF hybrid** (no embedding
  model). This keeps us trivially under the 150 MB cap and lets me finish
  with time left for the business artefact, which is weighted equally with
  the technical track.
- Wrote `src/generate_data.py`. The spec doesn't ship data, so the generator
  *is* the dataset — seed 42, 40 tenders in a 24/12/4 split of txt/html/pdf,
  25 EN / 15 FR (≈ spec's 60/40). fpdf2 for PDF writing is the lightest option.

### Hour 2 — Parsing, ranking, structured signals
- `src/parser.py`: `pypdf` for PDF, `bs4` for HTML, plain read for TXT; one
  regex per field. `langdetect` seeded for determinism.
- `src/ranker.py`: weighted sum of six signals with explicit class constants
  at the top of `Matcher` so weights are visible and retunable.
- Deliberate weight decisions:
  - BM25 = 0.35 (primary lexical signal)
  - TF-IDF char-ngram = 0.25 (cross-lingual safety net)
  - Sector = 0.20 (the dominant *structured* signal)
  - Budget/deadline/language = 0.20 combined (ranking refinement)

### Hour 3 — Summarizer, evaluator, CLI
- Template summariser in `src/summarizer.py`. Deterministic, multilingual,
  cites sector/budget/deadline every time, and includes the stretch-goal
  "why NOT" disqualifier.
- `src/evaluate.py`: MRR@5 and Recall@5 against `data/gold_matches.csv`, plus
  the 3 lowest-recall profiles as confusion cases.
- `matcher.py`: thin CLI over the three modules. Function
  `matcher.py::rank(profile)` is the public API named in the brief.

### Hour 4 — Docs & business artefact
- `village_agent.md`: three distribution options costed in RWF, explicit
  per-activation CAC numbers, and a recommendation with reasoning. This is
  the 20% rubric item the rubric calls a "KTT differentiator".
- README, SIGNED.md, this log.

## LLM / assistant tools used

| Tool | Why | How it changed the output |
|---|---|---|
| **Claude Sonnet 4.6** (via Claude Code) | Pair-programming, scaffolding, edge-case review | Drafted the initial `generate_data.py` and `ranker.py` structure; I rewrote the weights, swapped `TfidfVectorizer` from word to `char_wb` (for cross-lingual), and chose `rank_bm25` over `sklearn.text.CountVectorizer` manual BM25 because it matters for speed. |
| **Claude Opus 4.7** (follow-up session) | Reviewed ranking logic and summariser template for hallucination risk | Pushed me to make the summariser deterministic and template-based; flagged that LLM-generated summaries would break the <150 MB and <3 min constraints. |

I did **not** use: Copilot, Cursor, ChatGPT, any human pair-programmer.

## Three sample prompts I actually sent

1. **(Sonnet)** "Given the T2.2 brief pasted above, recommend a ranking stack
   that stays under 150 MB, supports EN and FR, and runs in <3 min on CPU.
   Justify the choice against sentence-transformers." → Got a clear BM25 +
   char-ngram recommendation with the specific argument about cross-lingual
   cognates that I ended up using in the README.
2. **(Sonnet)** "My summariser emits fluent French but the needs phrase is a
   whole sentence long and pushes past 80 words — what's the cleanest way to
   cap without killing meaning?" → Suggested truncating only the descriptive
   paragraph, leaving the title/warning lines uncapped. That's what shipped.
3. **(Opus)** "Review my `village_agent.md` cost model — is the RWF math
   reasonable for a Rwandan call centre operating at 500 cooperatives/week?"
   → Pushed back on my original 500 RWF/coop cost, pointed out I had
   double-counted agent supervision. Final number (297 RWF) is ~40% lower.

## One prompt I discarded

"Write an end-to-end matcher for the T2.2 brief." — Discarded because it
collapses every design decision into a single generation. I wouldn't have been
able to defend the weight choices or the cross-lingual rationale in the Live
Defence. Better to scaffold module-by-module and own each choice.

## Hardest decision

**Whether to use sentence-transformers.** The safe, conventional answer is
`paraphrase-multilingual-MiniLM-L12-v2` — it's 117 MB, fits the cap, and would
probably score ~0.95 on MRR@5. The cost is a 30-second cold start from disk,
a Python-level forward pass per query that dominates the latency budget, and
a harder story about reproducibility on a free Colab CPU.

I chose char-ngram TF-IDF + BM25 because the evaluation set is small (40
tenders) and the vocabulary overlap between EN and FR in this domain is high
(`agri`, `tech`, `solaire/solar`, `santé/health`). MRR@5 of 0.933 validated
that — the two profiles we miss (P02, P10) lose on ranking refinement, not on
recall of the sector. If the corpus grew to 4,000 tenders I'd revisit, but at
40 the char-ngram trick is both faster and defensible.
