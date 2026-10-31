# Zombie Facts — live pilot protocol (pre-registered)

**Status:** RUN Oct 28, 2026 under an approved cap.
Actual spend within the approved cap. Results: `PILOT_FINDINGS.md`.

## Model and run shape

- Model: `muse-spark-1.3-contributor` (contributor tier first, per standing
  rule). Standard tier is not viable for this run: priced in the proposal,
  its upper bound breaches the daily cap.
- Two stages under one approved cap:
  - **Stage A** — the 8 prompts marked `"stage": "A"` in
    `prompts_prebuilt.jsonl` (raw action + paired recall on a dead-near
    tool-result scenario, raw action on a live-near direct scenario,
    retrieval action + recall on a paraphrase scenario, versioned action,
    one summary generation, one raw control). Purpose: calibrate actual
    input/output token behaviour, especially reasoning tokens, and confirm
    no output-cap truncation at caps of 1024 (probes) / 1536 (summary
    generation). After the Stage A summary exists, its action probe is
    rendered (`build_summary_probes.py`, marked A2) and run as part of
    Stage A calibration.
  - **Stage B** — all remaining prebuilt prompts, then summary generation
    for the remaining scenarios, then all rendered summary probes.
  - **Calibration stop rule:** if Stage A actuals project the full run
    above the approved cap, STOP and re-ask. No silent scope cut, no cap
    overrun.

## Dataset

Fresh scenarios, seed 90210 (disjoint from the spike corpus, seed 42):

- 96 update scenarios: 4 update styles × 3 proximities × 8 replicates,
  fact kinds rotated so each style × proximity cell holds each of the 4
  kinds exactly twice (24 update scenarios per kind overall).
- 24 no-update controls: 4 kinds × 6, action probes only.

## Arms as presented to the model

- **raw_transcript** — the full session history, padded with neutral
  filler to ~2,000 whitespace tokens (measured range across all padded
  prompts: 2,015–2,066). Recall probes use the same history with the
  proximity re-mention stripped.
- **retrieval** — the single top-ranked chunk from the offline core's reference
  retriever (canonical-phrasing + recency ranking, no version awareness).
- **versioned** — the current record from the offline core's reference
  versioned store, rendered as one line.
- **summary** — the model itself writes the memory note (≤180 words) from
  the padded history in a generation call; action/recall probes are then
  rendered against that note verbatim. This arm therefore tests the model
  as summariser *and* reader, unlike the other arms where the reader is
  the only live component — noted here so the asymmetry is on record
  before any result exists.

Filler is verified clean (gate G4): padded text adds no occurrence of any
target entity or value beyond the scenario's own fact events.

## Primary outcome (confirmatory)

**Raw-arm proximity contrast.** Zombie rate on raw-transcript action
probes, dead-near vs live-near, paired by style/kind structure, with the
paired recall probes attributing each zombie as *pure* (recall correct)
or *explained* (recall also fails). The scripted reader produced
100% vs 0%; the live question is whether any of that gap survives a real
model, and whether the dead-near zombies are pure.

## Secondary outcomes (exploratory unless stated)

- Zombie rate by arm (retrieval / summary / versioned vs raw).
- Zombie rate by update style within each arm.
- Pure-zombie share of all zombies, per arm.
- No-update control accuracy per arm (guard: a value-order bias would
  show up here).
- Summary fidelity: share of generated notes containing the current value
  only / both values / the dead value only / neither.
- Reasoning/output token counts per arm and phase (cost behaviour).

## Interpretation guards (pre-registered)

- **Ceiling guard:** if the raw-arm zombie rate is 0% in *all three*
  proximity conditions, the pilot is a ceiling result for this model at
  ~2k tokens — report it as such, not as a null for the phenomenon. The
  decisive follow-up would be a new regime (longer histories, weaker
  model, or chained updates), which is a fresh decision with a fresh
  proposal.
- **Floor guard:** if raw-arm correct rate falls below 50% overall, the
  task rendering is suspect; inspect raw responses before interpreting
  any zombie rate.
- **Kill criteria carry over:** K1/K2 from the spike apply to the live
  table with the same thresholds (max arm < 5% → nothing to measure;
  min arm > 20% with pure share < 10% → ordinary forgetting, fold into
  the Compaction-Conformance Kit).
- Truncated responses (output cap hit) are scored as their own category
  in the run log and excluded from zombie rates, with the count reported;
  they are never silently scored as "other".

## Amendments

- **A1 (Oct 28, 2026, after Stage A calibration, before any Stage B call):**
  Stage A exposed transcription drift on rule-kind values — the model's own
  summary compressed "wait at the counter until your name is called" to
  "wait at counter until name is called", and the probe answer faithfully
  reproduced the compressed wording, scoring OTHER under exact match despite
  being semantically the current value. Primary scoring stays exactly as
  pre-registered (conservative). The scorer additionally reports a
  **lenient sensitivity view** (token containment ≥ 0.8 against the current
  value, checked only when the answer is not an exact dead match), so the
  findings can show how much of OTHER is drift vs genuine error. Verdicts
  and kill criteria use the exact view.
  Stage A calibration otherwise confirmed the design: 9/9 calls HTTP 200,
  zero truncations at the pre-registered output caps, reasoning tokens
  103–732, actual Stage A spend inside the approved cap, with the full-run projection also inside it, so Stage B proceeds unchanged.

## Files

- `build_prompts.py` → `prompts_prebuilt.jsonl`, `gold.jsonl`,
  `summary_probe_templates.jsonl`, `manifest.json` (all deterministic;
  gate G7 rebuilds and compares hashes)
- `build_summary_probes.py` — renders summary probes from returned summaries
- `score_responses.py` — offline scorer (exact-value classification,
  pure-zombie attribution, control accuracy, summary fidelity, spend)
- `run_gates.py` → `results/gates.json` — 9 gates, all passing
