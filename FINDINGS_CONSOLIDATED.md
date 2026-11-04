# Zombie Facts — consolidated findings

One benchmark, five measurements: an offline scripted core plus four live
runs. This file consolidates them; the per-run findings documents
(`pilot/PILOT_FINDINGS.md`, `pilot_v2/PILOT_FINDINGS_V2.md`,
`pilot_rep/PILOT_FINDINGS_REP.md`,
`pilot_emb/PILOT_FINDINGS_EMB_LOCAL.md`) carry the full detail, and the
per-run protocols carry the pre-registered decision rules.

## The question

When a fact is superseded, does an agent act on the current value or
the dead one? Two failure modes are distinguished throughout:

- **Store failure:** the memory system hands the reader the dead value
  (retrieval ranking, registration misses). The reader cannot do better
  than what it is shown.
- **Reader failure:** the reader is shown the full history, knows the
  current value when asked directly, and still acts on the dead value.
  Measured as **pure zombies** (action zombie + recall correct).

## Scripted core (Oct 26, 2026, offline)

280 scenarios, reference reader ("nearest encoded mention wins").
Retrieval 50.0%, raw 42.1%, summary 24.2%, versioned 8.3% zombie.
Verdict: GO — the effect exists at measurable size and separates
architectures. Scripted arms only; no claim about real models.

## v1 live pilot (Oct 28, 2026, 984 calls, ~2k tokens)

Single updates, explicitly labelled historical re-mentions.

| Arm | Zombie | Pure zombie | Controls |
|---|---:|---:|---:|
| raw_transcript | 0.0% | 0.0% | 100% |
| summary | 0.0% | 0.0% | 100% |
| retrieval | 50.0% | 0.0% | 100% |
| versioned | 6.3% | 0.0% | 100% |

Ceiling guard fired on the primary contrast: the live reader was
perfect on raw transcripts at this scale. Store susceptibility
confirmed (retrieval hands the reader the dead chunk); reader
susceptibility not observed — at this scale.

## v2 hard-regime pilot (Oct 29, 2026, 324 calls, ~20k tokens)

Chained updates v1→v2→v3, distractor facts, unlabelled re-mentions.

| Arm | Zombie | Pure zombie | Controls |
|---|---:|---:|---:|
| raw_transcript | 12.5% (6/48) | 8.3% (4/48) | 100% |
| retrieval (TF-IDF) | 72.9% (35/48) | 0.0% | 100% |
| versioned | 6.3% (3/48) | 0.0% | 100% |

The ceiling did not hold. All 6 raw zombies sat in one chain
(direct→paraphrase), all answering v2. The reader misses a final update
that arrives as a passing mention and falls back to the last
clearly-marked update. Retrieval: the reader used the retrieved chunk
faithfully in 48/48 probes; 12 dead choices were index-order ties, 23
were clear TF-IDF wins for the original plant chunk — the tie rule
alone does not explain the rate.

## Varied-phrasing replication (Oct 30, 2026, 104 calls)

Raw arm only. First update always direct; final update phrasing varied;
proximity fixed to none; ~20k tokens.

| Final phrasing | Zombie (action, truncated excluded) | Pure |
|---|---:|---:|
| v2 baseline paraphrase | 5/8 | 4 |
| aside ("By the way…") | 2/8 | 2 |
| hearsay ("I heard…") | 8/8 | 1 |
| parenthetical | 7/7 scored | 0 |
| imperative ("go with…") | 6/8 | 4 |
| direct (control) | 0/8 | 0 |

Pooled weak phrasings: 28/39 (71.8%) zombie, all v2, never v1.
Controls 8/8. Two responses truncated (reasoning to cap, empty answer),
excluded per protocol. The effect is not a single-template quirk, and
the direct control rules out position/length as the driver. A
dose-response by indirectness appears: the more embedded the value
(reported speech, parenthetical aside), the worse the reader does. And
two failure depths: stronger weak phrasings are registered but not used
at action time (pure); the weakest are not registered even on direct
recall (explained).

## Embedding-retriever pilot (Nov 1, 2026, 108 calls)

The v2 corpus reused exactly (823 chunks, 108 probes, same gold), with
the TF-IDF proxy replaced by a real embedding retriever: a local model
(all-MiniLM-L6-v2, CPU, 384-dim vectors, cosine top-1, the same 0.02
tie rule with earliest-index tie-break). Same reader, prompts, and
scoring as v2 retrieval.

| Arm | Zombie | Pure zombie | Controls |
|---|---:|---:|---:|
| retrieval (embedding, local) | 78.7% (37/47) | 12.8% (6/47) | 100% |

The headline is close to TF-IDF's 72.9%, so the proxy is validated as
a store-failure estimate — but the composition differs. Of the 37
scored zombies, 24 were tie-driven and 13 were clear wins:
clear-win-only rate 27.7%, below TF-IDF's 47.9%. That comparison is epsilon-dependent:
re-cutting the recorded margins at tighter thresholds lifts the
clear-win-only dead rate to 72.9% of choices at 0.002, above TF-IDF's
47.9% — so the figure must always be reported with its epsilon
(0.02 here). See the sensitivity section in the emb findings. Tied choices picked
the plant chunk in 39 of 48 ties, so the earliest-index tie-break
systematically favours the oldest value. The reader added no error:
faithful to the retrieved chunk in 106/107 responses (59/59 on action
probes), zero reader-introduced zombies. One action response
truncated (reasoning to cap, empty answer), excluded per protocol.
The chain pattern matches the raw-reader finding through retrieval:
chains ending in a weak final update ran 92–100% zombie, while the
chain ending in a strongly marked document-style final update ran
25%. Proximity was flat (73–83% everywhere), as expected from a
retriever that ignores position. The fix this points at is tie
behaviour (dense short-statement similarities plus the earliest-index
break), not confident misranking alone. The counterfactual (re-applying the tie rule
at other epsilons from saved rankings) qualifies that: tightening
to pure top-1 cuts retrieval dead from 38/48 to 32/48 with zero
breakage, so the tie-break is worth fixing, but the remaining 32
are confident misrankings — ranking quality, not tie-breaking, is
the bulk of the failure.

## What this does and does not establish

Establishes, for this model class at ~20k tokens with exact-value
instructions:

1. Version-blind retrieval manufactures zombies regardless of reader
   quality (50.0% v1, 72.9% v2 with a TF-IDF proxy, 78.7% with a local
   embedding retriever).
2. A versioned store with supersession links nearly eliminates them
   (6.3% in both pilots, matching its reference registration rate).
3. A raw reader misses weakly phrased final updates at high rates
   (up to 100% per phrasing at n=8), falling back to the last
   clearly-marked update — never to the oldest value.

Does not establish: rates for other models, other scales, prose (non
exact-value) answers, or production embedding retrievers — the TF-IDF
retriever here is a documented proxy, not a production index, and the
embedding pilot used one small local model, not a hosted embedder or
a production store. The per-phrasing rates are presence/absence
screens at n=8, not precise rankings.

## Reproduce

See `REPRODUCE.md`. The offline core, all gates, and all tests rerun
offline. Live reruns need your own model API key and your own spend
cap; the runners enforce the cap themselves.
