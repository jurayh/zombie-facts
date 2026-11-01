# PROTOCOL_EMB — Embedding-Retriever Pilot (pre-registered)

## Question

The v2 hard-regime pilot found a TF-IDF retrieval arm handing the reader
a dead chunk in 35/48 action probes (72.9%), with the reader faithful to
the retrieved chunk in 48/48 cases. TF-IDF is a proxy, not a production
retriever. This pilot asks: does a real embedding retriever do the same
thing, and how much of its zombie rate is tie-driven versus
clear-win-driven?

## Design (fixed before any run)

- **Corpus: not new.** pilot_v2's corpus, seed 777013, reused exactly:
  60 scenarios (48 updates, 12 controls), 823 fact-bearing chunks,
  108 retrieval probes (48 action + 48 recall on updates, 12 action on
  controls). Chunk identity and gold are verified by gates G2/G3.
- **Arm: retrieval only.** Raw and versioned arms are already measured
  in v2 and are not re-run here.
- **Retrieval:** top-1 cosine over whole-statement chunks, one query per
  probe (the probe task text). Tie rule identical to TF-IDF: margin
  below 0.02 means the earliest chunk in scenario order wins. The tie
  split is a primary output, not a footnote.
- **Reader prompts:** identical format to v2's retrieval prompts
  (ANSWER_INSTRUCTION + "Memory (retrieved record):" + chunk text +
  task), same reader model class, same exact-value scoring.
- **Backends:** one backend per run, reported separately, never pooled:
  - `local`: sentence-transformers on CPU, default all-MiniLM-L6-v2
    (override via EMB_LOCAL_MODEL). No money cost.
  - `api`: OpenAI-compatible embeddings endpoint (EMB_API_URL,
    EMB_API_MODEL, EMB_API_KEY, EMB_API_RATE_PER_M). Cap-enforced.
  - `stub`: gates and tests only. Stub results are never reported.

## Primary outcome

Embedding-retriever zombie rate on the 48 action updates, reported
with three splits, always together:
1. **Tie split:** zombie rate counting all dead choices, and counting
   clear wins only (margin >= 0.02).
2. **Dead split:** zombie_v1 vs zombie_v2.
3. **Other rate:** choices that are neither current nor dead
   (distractor entities), which TF-IDF kept near zero.

Comparison anchors (v2 TF-IDF retrieval, action updates):
- 72.9% dead (35/48); 12 tie-driven, 23 clear wins for the v1 plant
  chunk (clear-win-only rate 47.9%); reader faithful 48/48.

## Pre-registered interpretation bands (descriptive, not pass/fail)

- **Close to TF-IDF** (within ~10 points, similar tie split): the proxy
  is validated; the TF-IDF number stands as a store-failure estimate.
- **Clearly lower** (below ~50%): TF-IDF overstated store failure.
  Report both numbers, TF-IDF as an upper bound, and say so plainly.
- **Dead split shifts toward v2** (TF-IDF's clear wins were v1-heavy):
  embedding geometry ranks recency differently from keyword ranking.
  Report as a new finding, not as a contradiction of v2.
- **Reader faithfulness drops** below v2's 48/48: the reader stage, not
  the retriever, needs investigation before any store claim is made.

## Run shape

1. **Stage R** (run_retrieval_emb.py): embed chunks + queries, retrieve,
   write retrieval_choices_emb.jsonl and prompts_emb.jsonl, mark 8
   stage-A prompts spanning 2 dead_v1 / 2 dead_v2 / 2 current / 1
   control / 1 tie (shortfall filled in file order).
2. **Reader Stage A** (run_reader_emb.py --stage A): 8 calibration
   prompts. Stop rule: if spent + wave estimate exceeds the reader
   sub-cap, stop before the wave (same guard as v2).
3. **Reader Stage B**: remaining 100 prompts.
4. **Scoring** (score_emb.py): exact-value classification, pure/explained
   split via paired recall, control accuracy. Truncated responses are
   excluded and counted, per v2 protocol. The tie split is computed by
   joining choices and scores; it is part of the findings, not optional.

## Guards and failure handling

- **Controls:** if control accuracy is not 100%, investigate before
  reporting any zombie rate (same guard as v2).
- **Embedding failure:** if the backend errors, stop. No partial
  prompts file is scored; a re-run starts from a clean stage R.
- **Stub quarantine:** any result produced with backend=stub is a gate
  artifact, not a finding, and must not appear in findings.
- **One backend, one run:** running the second backend is a second run
  with its own approval and its own findings section.

## Honest limits (stated now, not discovered later)

- Chunking is whole statements. Real stores chunk differently (sliding
  windows, metadata, hybrid search), so this measures "embedding
  ranking over clean chunks", not any specific production store.
- One embedding model per run. Local and hosted models may disagree;
  that disagreement is itself informative and is why backends are never
  pooled.
- The reader is one model class. A different reader could be more or
  less faithful to a retrieved dead chunk.
- Mem0 / Zep / LangGraph stores are still untested after this pilot;
  this pilot replaces the ranking proxy, not the whole store.
