# Zombie Facts — live pilot findings

**Run:** Oct 28, 2026, under an approved cap ·
**Model:** `muse-spark-1.3-contributor`, temperature 0, reasoning low ·
**Actual spend within the approved cap** ·
859,168 input + 268,330 output tokens across 988 records (984 planned calls,
all completed; retries: 1 truncated summary generation, 2 empty/failed
retrieval probes, 1 HTTP 500 summary probe — all recovered inside the cap).

## Headline table (96 update scenarios per arm, exact scoring)

| Memory arm | Zombie rate | Correct | Other | Pure zombie rate | Control acc. |
|---|---:|---:|---:|---:|---:|
| retrieval | **50.0%** | 50.0% | 0.0% | 0.0% | 100% |
| versioned | **6.3%** | 93.8% | 0.0% | 0.0% | 100% |
| raw_transcript | **0.0%** | 100% | 0.0% | 0.0% | 100% |
| summary | **0.0%** | 90.6% (100% lenient) | 9.4% | 0.0% | 100% |

## Primary outcome: the ceiling guard fires

The pre-registered primary contrast was the raw-arm proximity effect. Live,
it is absent at every point:

| Raw arm, by proximity | Zombie | Correct |
|---|---:|---:|
| dead-near (n=32) | **0%** | 100% |
| live-near (n=32) | 0% | 100% |
| none (n=32) | 0% | 100% |

By update style the raw arm is likewise 100% correct across direct,
paraphrase, document, and tool_result. The manipulation that produced
100% zombies (80/80) in the scripted nearest-mention reader produced
**0/96** in the real model. Per `PROTOCOL.md`, this is reported as a
**ceiling result for this model at ~2,000 tokens** — not as a null for
the phenomenon in general. The model visibly uses the cues the scripted
reader ignored: the archive note's "historical / earlier" framing, the
update's supersession language, and session order. Its model-written
summaries do the same work explicitly — 92.7% of summary notes contain
both values, typically with the current one marked as superseding
(e.g. "Current rule supersedes earlier: …"), 0% contain the dead value
only. **Pure zombie rate is 0.0% in every arm**: nowhere did the model
act on a dead fact it could recall cleanly, because nowhere did it act
on a dead fact presented alongside its replacement.

## The zombies that did occur live in the store, not the reader

Retrieval (50.0%) and versioned (6.3%) zombie rates are real, but their
mechanism is different in kind from the scripted raw-arm effect: in those
arms the reader only ever sees the store's artifact, and the artifact
itself was wrong.

- **Retrieval 50.0%** — identical to the scripted arm's 50.0%. By style:
  direct 0%, document / paraphrase / tool_result 66.7% each. By proximity:
  dead-near and none 75%, live-near 0% (a canonical live confirmation
  chunk outranks the dead one). The reference retriever ranks the
  canonical-phrased dead chunk above the non-canonical live update; the
  model then faithfully answers from the only record it was handed.
- **Versioned 6.3%** (scripted: 8.3%) — 6 scenarios, both probes each,
  concentrated in tool_result updates (16.7%) and document (8.3%): the
  reference store's missed registrations, transmitted without added error.

So the live pilot *does* separate architectures (50.0 / 6.3 / 0 / 0), and
the separation survives contact with a real model — but for the distilled
arms it measures store-artifact fidelity, not reader susceptibility. The
one arm where the reader faced the contradiction directly is the arm
where the effect vanished.

## Secondary results

- **Summary arm**: 0% zombie. Exact-match "other" of 9.4% is entirely
  transcription drift under Amendment A1's lenient view (100% lenient
  correct): the model compresses rule values in its notes ("wait at the
  counter until your name is called" → "wait at counter until name is
  called") and answers with the compressed wording.
- **Controls**: 100% accuracy in all four arms — no value-order bias.
- **Reasoning tokens** averaged 193 (raw) to 291 (summary) per call, far
  below the Context-Topology-calibrated planning figures; that, plus a
  BPE ratio of ~1.11 vs the 1.4 upper bound assumed, is why actual spend
  landed well inside the expected estimate and the cap.
- One truncated response in 988 records (a summary generation whose
  reasoning hit the 1536 cap); retried successfully inside the cap and
  excluded from rates per protocol.

## Verdict vs the pre-registered criteria

- **K1** (max arm zombie < 5% → nothing to measure): does **not** fire —
  retrieval is at 50.0%.
- **K2** (min arm > 20% and pure share < 10% → ordinary forgetting):
  does **not** fire — two arms are at 0%.
- **Ceiling guard** (raw zombie 0% in all proximities): **fires.** The
  honest summary of the pilot is therefore two-part:
  1. *Reader susceptibility* — the headline phenomenon as originally
     framed (a model picking whichever version sits closer) — **not
     observed** in Muse Spark 1.3 at ~2k tokens with clean session
     structure and an exact-value instruction. Zero pure zombies in 384
     action probes.
  2. *Store susceptibility* — **confirmed live**: a version-blind
     retriever manufactures zombies at 50% on non-direct updates no
     matter how good the reader is, because the reader never sees the
     live fact. That is arguably the more actionable finding for memory
     system builders: at this scale, supersession fails at ranking and
     registration time, not at read time.

## What remains open (fresh decisions, not covered by this approval)

- Longer regimes: histories of 50k–200k tokens with many interleaved
  facts, where the update is genuinely hard to find.
- Chained updates (v1 → v2 → v3) and re-mentions *without* explicit
  "archive / historical" labelling — the cues this model leaned on.
- Weaker or smaller models, and instructions that ask for an action in
  prose rather than an exact value.
- A production retriever (embedding-based) in place of the reference
  keyword retriever, to price the 50% figure against a real stack.

Any of these is a new proposal with its own measured estimate and cap.
Nothing here is published and no repo exists; both remain the author's call.

## Files

- `responses.jsonl` — full run ledger (988 records, per-call tokens/cost)
- `results/pilot_scores.json` — scorer output · `results/breakdowns.json`
- `raw/` — raw API payloads per call
