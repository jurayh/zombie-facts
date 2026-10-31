# Zombie Facts — hard-regime pilot protocol v2 (pre-registered)

**Status:** package built and gate-verified offline on Oct 29, 2026.
**No model call has been made.** The run starts only on the author's explicit
approval of the cap in `PILOT_PROPOSAL_V2.md`.

## Why v2 exists

The v1 live pilot (Oct 28, 2026) hit its ceiling guard on the primary
question: the raw-arm reader scored 0 zombies in 96 probes, in every
proximity cell and style, at ~2,000 tokens with explicitly labelled
historical re-mentions. v2 removes the three cushions the model leaned
on, one at a time and all at once:

1. **Scale:** transcripts are ~20,000 whitespace tokens (measured range
   20,077–20,125), 10× v1, with distractor facts about other entities
   interleaved throughout — the target fact is buried, not nearly alone.
2. **Chains:** updates arrive as v1 → v2 → v3, so there are two dead
   values. Answering v2 (most recent dead) vs v1 (oldest dead) is scored
   separately; a recency-biased reader and a primacy-biased reader leave
   different signatures.
3. **Unlabelled re-mentions:** dead-near conditions restate an old value
   in passing ("a message in the thread mentions … in passing") with no
   archive / historical / earlier / superseded wording anywhere in the
   re-mention (gate G5). The v1 note was explicitly marked historical,
   and the live model used that cue.

## Dataset

Fresh scenarios, seed 777013 (disjoint from spike seed 42 and v1 seed
90210):

- 48 update scenarios: 4 chains × 4 proximities × 3 replicates, kinds
  rotated to 12 per kind.
  - Chains: direct→paraphrase, paraphrase→tool_result,
    document→direct, tool_result→document.
  - Proximities: dead_old (unlabelled mention of v1), dead_recent
    (unlabelled mention of v2), live_near (confirmation of v3), none.
- 12 no-update controls (3 per kind), action probes only.
- Every scenario has the same 8-session layout, so probe distance is
  held constant across proximity conditions.

## Arms

- **raw_transcript** — the full padded history (action) or the same
  history with the S6 re-mention replaced by filler (paired recall).
- **retrieval** — TF-IDF cosine retriever over every fact-bearing
  statement in the transcript (target + distractors), top-1 chunk, no
  version awareness. This replaces v1's canonical-phrasing keyword
  ranker as a closer proxy for a production embedding retriever.
  **Stated limit, on the record before any result:** when the top two
  chunks score within 0.02, the earliest-indexed chunk wins (index-order
  tie-break). Pre-run, that rule already decides 33 of 48 action choices
  toward v1 — so retrieval v2 results MUST be reported with the tie
  split (clear wins vs ties, in `retrieval_choices_v2.jsonl`), or the
  retrieval rate will overstate what a production retriever would do.
  An embedding retriever with a real index remains a further step, not
  something this proxy claims to be.
- **versioned** — reference store with the v1 registration table applied
  independently to both chain updates; the current record is the last
  registered value. Pre-run reference distribution: 45/48 current,
  3 dead_v2 — i.e. the v2 versioned zombie rate is expected near 6%,
  as in v1, unless the reader adds error.
- **summary — excluded by design.** v1 live showed the summary arm clean
  (0% zombie, 100% lenient correct), and model-written summaries over
  20k-token histories would dominate the run's cost without testing the
  primary question (reader susceptibility). Retesting it at this scale
  is a documented deferral.

## Primary outcome (confirmatory)

**Raw-arm zombie rate by proximity** (dead_old, dead_recent vs live_near,
none), with paired-recall attribution into pure vs explained zombies,
and the v1/v2 dead split.

## Pre-registered decision rule

- If the raw reader scores **0% zombie in all proximity cells** again:
  the reader thesis is **closed for this model class at the tested
  scales** (2k and 20k tokens, clean and hard regimes). The benchmark's
  honest scope becomes store/supersession only — publishable as that,
  or parked. It does not prove no model anywhere is reader-susceptible.
- If the raw reader scores **>0% in a dead-near cell with a non-trivial
  pure share** (recall correct, action zombie): the original thesis is
  alive, and the next decision is publication/repo, not another pilot.
- Secondary outcomes: retrieval zombie rate with tie split, versioned
  zombie rate, zombie rate by chain, control accuracy (guard: any
  value-order bias shows up here), reasoning tokens per arm.

## Interpretation guards

- **Ceiling guard:** raw 0% everywhere → ceiling result, reported as
  such (not a null), now at two scales.
- **Floor guard:** raw correct rate below 50% overall → the rendering
  is suspect; inspect responses before interpreting any zombie rate.
- **Kill criteria carry over** from v1 (K1: max arm < 5%; K2: min arm >
  20% with pure share < 10% → ordinary forgetting, fold into the
  Compaction-Conformance Kit).
- Truncated responses are excluded and counted, never silently scored.

## Run shape

- Model: `muse-spark-1.3-contributor`, temperature 0, reasoning low,
  output caps 1024 (action/recall) — same as v1.
- Stage A: the 8 prompts marked `"stage": "A"` (raw action + recall on a
  dead_old chain, raw action on dead_recent and live_near chains,
  retrieval action + recall, versioned action, one raw control).
  Stage B: the remaining 316 prompts.
- **Calibration stop rule:** if Stage A actuals project the full run
  above the approved cap, STOP and re-ask. No silent scope cut, no cap
  overrun.

## Files

- `generator_v2.py` — chained scenarios, distractors, padding
- `retriever_v2.py` — TF-IDF retriever + tie rule
- `build_prompts_v2.py` → `prompts_v2.jsonl`, `gold_v2.jsonl`,
  `retrieval_choices_v2.jsonl`, `manifest_v2.json`
- `score_v2.py` — offline scorer (v1/v2 dead split, pure attribution)
- `run_pilot_v2.py` — cap-enforcing runner (NOT run)
- `run_gates_v2.py` → `results/gates_v2.json` — 10 gates, all passing
