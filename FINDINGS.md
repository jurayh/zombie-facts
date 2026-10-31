# Zombie Facts — spike findings

**Date:** Oct 26, 2026 · **Spend:** none (no model calls) · **Location:** `~/workspace/zombie-facts/`

## The question

Does the zombie effect — an agent acting on a superseded fact despite a live
replacement in memory — exist at measurable size, and does it separate memory
architectures? If it is near zero everywhere, there is nothing to measure
(kill K1). If it is high everywhere and fully explained by v2 recall failure,
it is ordinary forgetting and belongs in the Compaction-Conformance Kit
(kill K2).

## What was built

- **Generator** (`zombie_facts/generator.py`): 280 scenarios, seed 42.
  240 update scenarios in a balanced factorial design — 4 fact kinds
  (address, price, schedule, rule) × 4 update styles (direct, paraphrase,
  document, tool result) × 3 proximity conditions (dead-near, live-near,
  none) × 5 replicates — plus 40 no-update controls. Every scenario is a
  6-session history: plant v1, filler, update to v2, filler, optional
  proximity re-mention, then the probe. Ground truth is structural.
- **Four reference memory arms** (`arms.py`): raw transcript, summary
  memory, retrieval store (canonical-phrasing + recency ranking, no version
  awareness), versioned store with supersession links. Each arm's
  update-registration behaviour is a stated, style-dependent parameter
  table in the code — a reader can disagree with the numbers; the harness
  is what is on trial.
- **Reference reader** (`agents.py`): *nearest encoded mention wins* — the
  HN claim under test, operationalised — with style-dependent encoding
  misses for the update event itself (a merely-seen tool result is encoded
  less reliably than a direct statement). Oracle and primacy readers serve
  as sanity instruments.
- **Controls** (`harness.py`): every action probe is paired with a
  v2-recall probe (same scenario, re-mention stripped, direct current-value
  question), splitting zombies into **pure** (recall OK, action zombie —
  the agent *had* the live fact and still acted on the dead one) and
  **explained** (recall also fails). No-update controls check that arms
  are not simply biased toward second values. The proximity manipulation
  re-mentions the dead fact historically (dead-near) or confirms the live
  one (live-near) just before the probe.
- **Tests**: 10 unit tests pass, including generator balance, ground-truth
  integrity, per-arm behaviour on hand-built scenarios, and full-run
  determinism. Results are byte-identical across repeated runs
  (md5 `312826ce…` for `zombie_rates.json`, verified ×3).

## First zombie-rate table (scripted/reference arms)

240 update scenarios per arm; full table in `results/zombie_rates.md`.

| Memory arm | Zombie rate | Correct | v2 recall failure | Pure zombie rate | Control acc. |
|---|---:|---:|---:|---:|---:|
| retrieval | **50.0%** | 50.0% | 75.0% | 0.0% | 100% |
| raw_transcript | **42.1%** | 57.9% | 27.9% | 23.8% | 100% |
| summary | **24.2%** | 75.8% | 35.0% | 0.0% | 100% |
| versioned | **8.3%** | 91.7% | 12.9% | 0.0% | 100% |

Arm separation: **41.7 points** (retrieval 50.0% − versioned 8.3%).

Patterns that carry the signal:

- **Proximity is decisive on the raw transcript** — exactly the thread's
  claim. Dead-near: **100%** zombie (80/80). Live-near: **0%**. None:
  26.2%, and those 21 zombies are all recall-explained (the reader missed
  the update's encoding). All 57 pure zombies in the entire run live in
  the raw × dead-near cell: a historical re-mention of the dead fact,
  placed nearest the probe, overrides a live update the same reader
  demonstrably *can* recall when the re-mention is stripped.
- **Update style orders every arm the same way**: direct is safest,
  tool_result is the most zombie-prone (raw 33.3% → 55.0%; summary 1.7% →
  45.0%; versioned 0% → 20.0%). Retrieval is flat 66.7% for every
  non-direct style — its failure is phrasing ranking (the canonical dead
  chunk outranks the non-canonical live one), not style encoding.
- **Failure modes differ by architecture, which is the point of the
  benchmark.** Raw fails by proximity (pure zombies). Summary fails by
  extraction (its zombies are recall-explained: the update never made the
  note). Retrieval fails by ranking (likewise recall-explained under this
  attribution, because the same ranking serves both probes). Versioned
  fails least and only by missed registration (tool_result 20.0%,
  paraphrase 10.0%).

Sanity gates: oracle reader scores 0 zombies; primacy reader scores 100%
zombies on the raw arm; all arms score 100% on no-update controls.

## Verdict vs the pre-registered kill criteria

**GO — neither kill fires.**

- K1 (near zero everywhere) fails clearly: max arm zombie rate is 50.0%.
- K2 (high everywhere *and* fully recall-explained) fails on both legs:
  the versioned arm is at 8.3% (not high everywhere), and pure zombies are
  19.1% of all zombies (57 of 299), concentrated in one interpretable
  cell (raw × dead-near) rather than smeared as generic forgetting.

Under the scripted reader the zombie effect exists at measurable size,
separates the four architectures by 41.7 points, and includes a component
that is *not* forgetting: acting on a dead fact that the same system can
produce on a clean recall probe, because a historical mention of it sat
nearest the probe.

## What this does NOT show

These are reference implementations under a stated reader model, not real
systems. The extraction/miss/ranking parameters in `arms.py` and
`agents.py` are assumptions, chosen to be plausible and printed in full;
different parameters would move the rates (the unit tests pin the extremes:
oracle 0%, primacy 100%). The spike proves the *instrument*: generator,
controls, attribution, and scorer work end to end, are deterministic, and
can separate architectures and register a pure-supersession component when
one is present. Whether real LLMs on real memory stacks show the effect —
and at what size — is exactly what the live arm would measure.

## Live-arm proposal (for approval; NOT run)

Measured from the generated corpus, not guessed:

- Mean raw-transcript presentation is 431 chars ≈ **108 tokens**; with
  instructions + probe, ≈ 160 input tokens and ≈ 15 output tokens per call.
- Faithful live version of this dataset: 240 update scenarios × 2 probes ×
  4 arms = 1,920 calls ≈ 307k input + 29k output tokens. At contributor
  rates, that stays well within a daily cap.
- More realistic variant worth considering: pad filler sessions to
  ~2,000 tokens per presentation (real session lengths) → ≈ 3.8M input
  tokens, still far under the daily cap.
- Suggested shape: one model (contributor tier first), raw + retrieval +
  versioned presentations rendered as text, summary arm rendered from a
  model-written summary (that adds ≈ 240 summary-generation calls,
  at toy length or padded). Total either way stays well under the daily cap.

No live run happens without the author's explicit approval of one of these
shapes (or a revised one).

## Files

- `README.md` — design and kill criteria
- `zombie_facts/` — generator, arms, agents, harness (stdlib only)
- `run_spike.py` — regenerates `results/zombie_rates.{json,md}`
- `tests/test_zombie.py` — 10 tests, all passing
- Nothing published, no repo created — that is the author's call.
