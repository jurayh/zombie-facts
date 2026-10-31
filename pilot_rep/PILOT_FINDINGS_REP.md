# Zombie Facts — varied-phrasing replication findings

**Run:** Oct 30, 2026, under an approved cap.
**Model:** `muse-spark-1.3-contributor`, temperature 0, reasoning low,
output caps 1024. **Calls:** 104/104 completed.
**Spend within the approved cap.** Stage A: 8 calls, 0
truncations; projection to the full run inside the cap, so
Stage B proceeded unchanged. Tokens: 2,413,377 input / 40,348 output
(input at 1.154× the whitespace count, matching v2's 1.155).

**Scoring note:** 2 responses hit the 1024-token output cap with all
reasoning tokens and an empty answer (one parenthetical action, one
imperative recall). Per protocol they are excluded and counted, never
scored: 47 action updates scored, not 48. Both sat in weak-final
scenarios — the model reasoned to exhaustion without answering — but
they are not counted as zombies.

## Results (raw arm only, action probes, truncated excluded)

| Final phrasing | Zombie | Correct | Pure zombies |
|---|---:|---:|---:|
| weak_baseline (v2 template) | 5/8 (62.5%) | 3/8 | 4 |
| weak_aside ("By the way…") | 2/8 (25.0%) | 6/8 | 2 |
| weak_hearsay ("I heard…") | 8/8 (100%) | 0/8 | 1 |
| weak_parenthetical | 7/7 (100%) | 0/7 | 0 |
| weak_imperative ("go with…") | 6/8 (75.0%) | 2/8 | 4 |
| **direct (control)** | **0/8** | **8/8** | 0 |
| **All weak (pooled)** | **28/39 (71.8%)** | 11/39 | 11 |
| **All update scenarios** | 28/47 (59.6%) | 19/47 | 11 (23.4% of scored) |

Controls: 8/8 correct. Every zombie answered v2 — never v1, in all 28
cases. Other rate 0.0%: every scored answer was exactly a current or
dead value.

## Decision rule outcome: the effect generalizes

All five weak phrasings produced zombies, against 0/8 for the direct
control. The pre-registered "effect generalizes" branch fires: the v2
chain-A effect is **not a single-template quirk**. Proceed to
publication with the stronger claim.

## Two findings inside the headline

**1. A dose-response by indirectness.** The more embedded the value,
the worse the reader does: hearsay and parenthetical — where the value
sits inside reported speech or a parenthetical aside — were missed
every time (8/8, 7/7). The aside ("By the way, X is Y now") was missed
least (2/8): it still carries "now" and addresses the reader directly.
The baseline (5/8) replicates v2's chain-A rate (6/12) closely.

**2. Two failure depths.** For the stronger weak phrasings (baseline,
imperative, aside), most zombies are pure: the reader answers v3
correctly on direct recall but acts on v2 (baseline 4/5 pure,
imperative 4/6, aside 2/2). For the weakest phrasings (hearsay 1/8 pure,
parenthetical 0/7), the recall probe fails too — the final update is
not registered as current at all, even when asked directly. So weak
phrasing fails in two ways: not used at action time, and (weaker still)
not encoded in the first place.

## Floor guard: triggered numerically, cleared on inspection

The protocol's floor guard (raw correct rate below 50% overall) fires
mechanically: overall correct is 19/47 = 40.4%, because weak phrasings
dominate the design (39 of 47 scored actions). The guard requires
inspection before interpreting, and the inspection clears it: controls
8/8, direct control 8/8, other rate 0.0% — the rendering is intact and
every answer is an exact value. The low correct rate *is* the effect
(zombie rate 59.6%), not a rendering failure. This is recorded rather
than hidden, because the guard's wording did not anticipate a design
where the effect itself pushes correct below 50%.

## Limits (stated, not buried)

- One model, one contributor-tier id, synthetic transcripts, exact-value
  instruction. Per-phrasing n = 8 (7 scored for parenthetical) is a
  presence/absence screen, as pre-registered — the gradient across
  phrasings is a pattern, not a precise rate ranking.
- The direct control rules out position/length as the driver (same
  position, same length regime, 0/8), but the claim remains about this
  model class at ~20k tokens.
- Scores in `results/pilot_scores_rep.json`; raw responses in
  `responses_rep.jsonl`.
