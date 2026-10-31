# Zombie Facts — live pilot proposal (approval request)

**Status: APPROVED Oct 28, 2026 and RUN under an approved cap.**
See `PILOT_FINDINGS.md`.

## What would run

- Model: `muse-spark-1.3-contributor` — contributor-tier pricing.
- **984 calls total**, all prompts built and measured locally:
  - 768 prebuilt prompts in `prompts_prebuilt.jsonl` (raw / retrieval /
    versioned action + recall probes; summary-generation prompts;
    no-update control action probes)
  - 216 summary-arm probes, rendered from the model's own summaries by
    `build_summary_probes.py` once generation responses exist
- Structure: Stage A = 8 calibration calls (+1 rendered summary probe),
  then Stage B, with a stop-and-re-ask rule if Stage A actuals project
  above the cap. Full design in `PROTOCOL.md`.

## Measured tokens

Input tokens are measured on the built corpus (whitespace count), then
bounded by a conservative 1.4× BPE upper bound estimate, the same convention as the
Context Topology Lab pilots, because the model's own tokenizer cannot be
consulted without a paid call.

| Component | Tokens |
|---|---:|
| Prebuilt prompts (whitespace, exact) | 708,840 |
| Summary probes (estimated: template overhead + 250-word summary allowance × 216) | 63,396 |
| **Total input (whitespace)** | **772,236** |
| **Total input (1.4× BPE upper bound)** | **1,081,130** |

Output tokens cannot be measured before any call exists. Planning figures
are calibrated on the Context Topology Lab pilots on this same model,
where reasoning tokens ran ~410–900 per prompt:

| Output assumption | Tokens |
|---|---:|
| Expected: 650/probe call × 864, 900/generation × 120 | 669,600 |
| Upper: output caps 1024/probe, 1536/generation | 1,069,056 |

| Total | Tokens |
|---|---:|
| Input at BPE upper bound | 1,081,130 |
| **Expected total (upper input + expected output)** | **1,750,730** |
| **Upper-bound total (upper input + capped output)** | **2,150,186** |

## Cap requested

**An approved total cap** for the whole pilot (Stage A + Stage B, all 984 calls) —
set with headroom over the upper-bound estimate. If Stage A calibration
projects above the cap, the run stops and comes back for a new decision
instead of overrunning or silently cutting scope.

Standard-tier comparison (`muse-spark-1.3`, standard-tier rates):
the upper bound alone breaches
the daily cap, which is why contributor tier is the only
viable route, consistent with the standing contributor-first rule.

## What approval covers, and what it does not

- Covers: the 984 calls above on the contributor model id, inside the
  approved cap, scored by `score_responses.py`, reported against the
  pre-registered primary contrast and guards in `PROTOCOL.md`.
- Does not cover: any second model, any rerun, any scope expansion, or
  publication. Each of those returns as its own decision.
