# Backend restructure — FAIR-R²L de-duplication, Trust parking, single European LLM

This branch restructures the assessment backend to match the reviewed IP4OS
concept (ReuseReady). No frontend changes yet — the dashboard still works.

## 1. FAIR-R²L no longer double-assesses FAIR
Previously FAIR was computed **twice**: once by F-UJI (its own panel) and again,
independently, from metadata inside the FAIR-R²L checklist. Vanessa flagged this
duplication.

Now: **FAIR-R²L = FAIR (from F-UJI) + AI Readiness + Responsible Licensing.**
- `fair_r2l_checklist.json` drops the Findable / Accessible / Interoperable /
  Reusable sections. It keeps only `ai_readiness` and `responsible_licensing`
  (the IP4OS-specific layers). The one genuinely-human FAIR reuse-permission
  check was preserved as a critical `RL_ACCESS` question under Responsible
  Licensing.
- `fair_r2l_scorer.py` gains `_fair_sections()`, which reads the four FAIR
  dimensions straight from the F-UJI result (`dimensions.<dim>.percent/level`)
  and merges them into `sections`. Overall readiness is the equal-weight mean of
  all six dimensions. `fair_source` is reported (`f-uji`, or
  `metadata-fallback` when F-UJI is unavailable — `fair_scorer` already produces
  the same shape from metadata as a fallback).
- Result: no aspect is scored twice; the FAIR number has a single source.

## 2. Trust / AI-generated-text analysis parked (out of scope)
The tool assesses the **resource** behind a link, not the user's own text, so the
Trust pipeline (HF claim classifier, bias/emotion model, sentence-embedding fact
verification, flan-t5 summary) is out of core scope.
- New flag `ENABLE_TRUST_ANALYSIS` (default **false**) in `config.py`.
- `unified_analysis.analyze_trust()` returns a `disabled` result when off, and the
  heavy `analysis_core` import is now **lazy** — so the main path never loads
  `transformers` / `sentence-transformers`. `app.py` (the legacy Streamlit Trust
  UI) uses a lazy wrapper for the same reason. Nothing is deleted; set the flag
  to `true` to re-enable.

## 3. One European language model, wording only
- `config.py` now centres on **Mistral** (`LLM_PROVIDER`, `LLM_MODEL`,
  `MISTRAL_API_KEY`); the unused `OPENAI_API_KEY` is deprecated.
- New `llm.py` is the single client. It is used **only** for wording (questions,
  explanations, plan text) and returns `None` when unconfigured so callers fall
  back to rule-based text. No score ever depends on it.

## Tests
`python test_refactor.py` — 18 checks covering: FAIR consumed from F-UJI,
readiness follows F-UJI, metadata-fallback flagged, checklist carries no FAIR
sections, and the main path importing without loading `transformers`.
