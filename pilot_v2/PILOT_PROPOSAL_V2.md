# Zombie Facts — hard-regime pilot proposal v2 (approval request)

**Status: NOT RUN. No model call has been made.** This proposal asks for
approval of a total cap; the run itself, Stage A included, starts only on
the author's explicit go.

## What would run

- Model: `muse-spark-1.3-contributor` — contributor-tier pricing.
- **324 calls total**, all prompts built and measured locally:
  48 update scenarios × 3 arms × 2 probes (action + recall) = 288, plus
  12 controls × 3 arms (action only) = 36.
- Structure: Stage A = 8 calibration calls, then Stage B = 316, with a
  stop-and-re-ask rule if Stage A actuals project above the cap. Full
  design and decision rule in `PROTOCOL_V2.md`.

## Measured tokens

Input tokens are measured on the built corpus (whitespace count), then
bounded by a conservative 1.4× BPE upper bound estimate — the same convention as
the v1 pilot, where the realised BPE ratio was ~1.11, so the bound is
genuinely conservative.

| Component | Tokens |
|---|---:|
| Prompts (whitespace, exact) | 2,182,801 |
| **Input (1.4× BPE upper bound)** | **3,055,921** |

Output tokens cannot be measured before any call exists. Planning figures
use the v1 pilot's actuals (reasoning ~190–290 per call at 2k tokens),
raised for the 10× longer histories:

| Output assumption | Tokens |
|---|---:|
| Expected: 500/call × 324 | 162,000 |
| Upper: output caps 1024/call × 324 | 331,776 |

| Total | Tokens |
|---|---:|
| Input at BPE upper bound | 3,055,921 |
| **Expected total (upper input + expected output)** | **3,217,921** |
| **Upper-bound total (upper input + capped output)** | **3,387,697** |

## Cap requested

**An approved total cap** for the whole run — set with headroom over the
upper-bound estimate. If Stage A calibration projects above the cap, the
run stops and comes back for a new decision instead of overrunning or
silently cutting scope.

Standard-tier comparison (`muse-spark-1.3`, standard-tier rates):
the upper bound alone breaches
the daily cap, which is why contributor tier is the only
viable route, consistent with the standing contributor-first rule.

## What approval covers, and what it does not

- Covers: the 324 calls above on the contributor model id, inside the
  approved cap, scored by `score_v2.py`, reported against the
  pre-registered primary contrast and decision rule in `PROTOCOL_V2.md`.
- Does not cover: any second model, any rerun, any scope expansion
  (including re-adding the summary arm), or publication. Each of those
  returns as its own decision.
