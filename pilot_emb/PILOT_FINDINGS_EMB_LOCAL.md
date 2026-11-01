# PILOT FINDINGS — Embedding Retriever, Local Backend (all-MiniLM-L6-v2)

## Run

- Backend: `local`, sentence-transformers 6.2.0 / torch 2.15.0+cpu,
  model all-MiniLM-L6-v2, 384-dim normalised vectors, cosine top-1,
  tie epsilon 0.02 with earliest-index tie-break (same rule as TF-IDF).
- Corpus: v2 corpus reused exactly (seed 777013): 60 scenarios,
  823 chunks, 108 retrieval probes.
- Reader: muse-spark-1.3-contributor, same prompts format and scoring
  as v2 retrieval. Stage A 8 prompts, Stage B 100 prompts.
- Spend: within the approved reader sub-cap (tokens: input 8,671,
  output 28,807). Embedding stage: no money cost.
- Responses: 108/108 HTTP 200, 1 truncation (pilot2-upd-028 action,
  reasoning to cap, empty answer), excluded per protocol. Scored: 107
  (47 action updates, 48 recall updates, 12 controls).

## Headline results (action updates, scored n=47)

| Arm | Zombie rate | Clear-win-only | Correct | Controls |
|---|---|---|---|---|
| Embedding (local) | 37/47 = 78.7% | 13/47 = 27.7% | 10/47 = 21.3% | 12/12 = 100% |
| TF-IDF (v2) | 35/48 = 72.9% | 23/48 = 47.9% | — | 100% |

Zombie split: v1 26/47 (55.3%), v2 11/47 (23.4%). Other rate 0.0%.

## Tie split (the finding inside the headline)

- Retrieval choices on action updates: 38/48 dead (79.2%), of which
  24 tie-driven and 14 clear wins. The truncated action probe accounts
  for the 38 vs 37 difference between choices and scored answers.
- Tied choices pick the plant chunk in 39/48 ties. The earliest-index
  tie-break systematically favours v1, because the plant chunk is the
  earliest chunk in scenario order.
- Reader-side tie split of the 37 scored zombies: 24 tie-driven,
  13 clear wins. Clear-win-only zombie rate 27.7%, below TF-IDF's
  47.9%.

Interpretation against the pre-registered bands (PROTOCOL_EMB.md):
the headline is close to TF-IDF (within ~10 points), so the proxy is
validated as a store-failure estimate — but the composition differs.
TF-IDF's failures were mostly confident; the embedder's failures are
mostly ties. A reader-facing fix that only addresses confident
misranking would miss most of the embedding retriever's failures;
the tie behaviour (dense short-statement similarities + earliest-index
break) is the thing to fix.

## Reader faithfulness: the reader adds no error

- Normalised faithfulness to the retrieved chunk: 106/107 overall,
  59/59 on scored action probes.
- Reader-introduced zombies (choice current, answer dead): 0.
- All 10 correct action answers came from current choices; all 37
  zombie answers came from dead choices.
- The single non-faithful response (upd-005 recall) echoed the
  retrieved chunk's value with trailing words ("in passing") and
  scored "other". Immaterial at 1/107.
- Pure zombies: 6/47 (12.8%) — action zombie with paired recall
  correct. Recall arm: 7 correct, 35 zombie_v1, 5 zombie_v2, 1 other
  (recall zombie rate 40/48 = 83.3%).

## Breakdowns

By chain (final update style is the second element):
- direct -> paraphrase: 12/12 zombie (100%)
- document -> direct: 11/11 zombie (100%)
- paraphrase -> tool_result: 11/12 zombie (91.7%)
- tool_result -> document: 3/12 zombie (25.0%)

The outlier is the chain ending in a document-style final update:
strongly marked finals are retrieved correctly. Weak finals
(paraphrase, tool_result) are where embedding retrieval fails — the
same shape as the raw-reader finding, now through retrieval.

By proximity: flat, 72.7%–83.3% across dead_old, dead_recent,
live_near, none. Position does not matter to a retriever, as expected;
this contrasts with the scripted raw arm, where proximity dominated.

## Guards

- Controls 100% (12/12). Floor guard not fired.
- Truncation handling per protocol (1 excluded, counted).
- No stub-backend results appear anywhere in this report.

## Limits (carried from the protocol)

- One small open embedding model. A frontier hosted embedder may rank
  differently; that is the cloud complement, not this run.
- Whole-statement chunking only; real stores chunk differently.
- One reader model class; reader faithfulness here (near-perfect)
  matches v2's 48/48, so the store-side result is not a reader artifact
  in this setup.
- Tie epsilon 0.02 was inherited from TF-IDF for comparability. The
  high tie density (48/108 choices) suggests the epsilon interacts
  with embedding geometry; a sensitivity analysis over epsilon is a
  natural zero-cost follow-up on the recorded scores, not a new run.
