# PILOT_PROPOSAL_EMB — Embedding-Retriever Run

## What is being proposed

Run the embedding-retriever pilot defined in PROTOCOL_EMB.md: replace
the TF-IDF proxy with a real embedding retriever on the v2 corpus, then
run the same reader over the retrieved chunks. Two stages:

- **Stage R:** embed 823 chunks + 108 queries, retrieve top-1 per probe,
  build 108 reader prompts.
- **Reader stages A/B:** 108 reader calls on the same model class as
  v2 (muse-spark-1.3-contributor), exact-value scoring, tie split and
  dead split reported with the headline rate.

## Measured inputs (not estimates)

- Chunks: 823; queries: 108; whitespace tokens: 12,438
  (10,980 chunk + 1,458 query).
- Embedding upper token bound (whitespace x 1.4): 17,413 tokens.
- Reader prompts are short retrieval prompts (one chunk + one task),
  the same shape as v2's retrieval prompts. The reader runner's wave
  estimate uses 1024 output tokens as a worst case, which is far above
  the short exact-value answers actually produced.

## Options (pick one backend; approval covers one run)

### Option A — local backend (recommended)

- Backend: sentence-transformers on CPU, default all-MiniLM-L6-v2.
- Money cost: none. One-time model download (~90 MB) and CPU time,
  which is not yet timed; the corpus is small (823 short chunks), so
  this is a minutes-scale job, timed on the first run.
- No key needed. No API spend. The only spend is the reader stage,
  inside its approved sub-cap.
- Why recommended: zero spend, no key handling, fully reproducible
  from the model id recorded in the choices file.

### Option B — hosted embedding API

- Backend: OpenAI-compatible endpoint, model and rate confirmed at
  approval time (EMB_API_MODEL, EMB_API_RATE_PER_M, EMB_API_KEY).
- Rate bound: the embedding stage stays inside its approved
  sub-cap at any rate below the bound implied by the token total
  above. The runner refuses to call the API if the projected cost
  from the confirmed rate exceeds the sub-cap.
- Reader stage: same approved sub-cap as Option A.

## Caps requested (embedding sub-cap + reader sub-cap, set at approval)

- Stage R embedding sub-cap (API backend only; local costs nothing).
- Reader sub-cap (enforced by run_reader_emb.py, set at approval).
- Approval covers: one backend, stage R, reader stages A and B, and
  scoring. It does not cover a second backend run, a different reader
  model, Mem0/Zep, or a repo push (separate decisions, as before).

## What approval is NOT needed for

Building this package cost nothing and is done: inventory, retriever,
runners, gates (15/15), tests (10/10), protocol. Nothing has been
embedded, retrieved, or read by a live model yet; no prompts_emb.jsonl
or responses_emb.jsonl exists.

## Risks, plainly

- Local model quality: all-MiniLM-L6-v2 is a small open model, not a
  frontier embedder. A low zombie rate here would show that *this*
  embedder ranks better than TF-IDF, not that all embedders do. The
  hosted option is the hedge; running both (separate approvals) is the
  strongest version of this pilot.
- Chunking: whole statements only. A real store's chunking could
  change the result in either direction; that limit is pre-registered
  in the protocol and must stay in any write-up.
