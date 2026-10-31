# Zombie Facts — varied-phrasing replication proposal (approval request)

**Status: NOT RUN. No model call has been made.** This proposal asks for
approval of a total cap; the run itself, Stage A included, starts only on
the author's explicit go.

## What would run

- Model: `muse-spark-1.3-contributor` — contributor-tier pricing.
- **104 calls total**, all prompts built and measured locally, raw arm
  only: 48 update scenarios × 2 probes (action + recall) = 96, plus 8
  controls (action only) = 8.
- Structure: Stage A = 8 calibration calls, then Stage B = 96, with a
  stop-and-re-ask rule if Stage A actuals project above the cap. Full
  design and decision rule in `PROTOCOL_REP.md`.

## Measured tokens

Same convention as v1/v2: input measured on the built corpus (whitespace
count), bounded by a conservative 1.4× BPE upper bound estimate. Realised ratios
were 1.11 (v1) and 1.155 (v2), so the bound is genuinely conservative.

| Component | Tokens |
|---|---:|
| Prompts (whitespace, exact) | 2,091,281 |
| **Input (1.4× BPE upper bound)** | **2,927,793** |

| Output assumption | Tokens |
|---|---:|
| Expected: 500/call × 104 | 52,000 |
| Upper: output caps 1024/call × 104 | 106,496 |

| Total | Tokens |
|---|---:|
| Input at BPE upper bound | 2,927,793 |
| **Expected total (upper input + expected output)** | **2,979,793** |
| **Upper-bound total (upper input + capped output)** | **3,034,289** |

## Cap requested

**An approved total cap** for the whole run — set with headroom over the
upper-bound estimate. If Stage A calibration projects above the cap, the
run stops and comes back for a new decision instead of overrunning or
silently cutting scope.

Standard-tier comparison (`muse-spark-1.3`, standard-tier rates):
inside the daily cap, but
contributor tier is used anyway per the standing contributor-first rule
(the content here is synthetic transcripts, no privacy reason to use
standard tier).

## What approval covers, and what it does not

- Covers: the 104 calls above on the contributor model id, inside the
  approved cap, scored by `score_rep.py`, reported against the
  pre-registered decision rule in `PROTOCOL_REP.md`.
- Does not cover: any second model, any rerun, any scope expansion
  (including re-adding retrieval/versioned arms), or publication. Each
  of those returns as its own decision.
