# Zombie Facts — hard-regime pilot v2 findings

**Run:** Oct 29, 2026, under an approved cap.
**Model:** `muse-spark-1.3-contributor`, temperature 0, reasoning low,
output caps 1024. **Calls:** 324/324 completed, 0 truncations.
**Spend within the approved cap.** Stage A: 8 calls, 0
truncations; projection to the full run inside the cap, so
Stage B proceeded unchanged. No protocol amendment was needed: exact
scoring was clean (other rate 0.0% in every arm), so the lenient drift
view from v1's Amendment A1 was not invoked.

**Tokens (actual):** 2,522,174 input / 86,055 output (avg 266 output per
call, below the planned 500). Input ran at 1.155× the whitespace count
(2,182,801), close to v1's 1.11 and well inside the 1.4× pricing bound.

## Results (48 update scenarios per arm, exact scoring)

| Arm | Zombie | Correct | Pure zombie | Control acc. |
|---|---:|---:|---:|---:|
| raw_transcript | **12.5%** | 87.5% | 8.3% | 100% |
| retrieval (TF-IDF) | **72.9%** | 27.1% | 0.0% | 100% |
| versioned | **6.3%** | 93.8% | 0.0% | 100% |

## The headline: the reader thesis is alive

The v1 ceiling did **not** hold at hard regime. The raw reader produced
**6 zombies in 48 action probes (12.5%)**, where v1 produced 0 in 96.
Per the pre-registered decision rule in `PROTOCOL_V2.md`, a raw rate
above 0% in dead-near cells with a non-trivial pure share revives the
original thesis. **Pure zombie rate 8.3% (4 of 48):** in those 4 cases
the reader answered v3 correctly on the paired recall probe (re-mention
stripped) yet acted on a dead value in the action probe — the textbook
pure zombie, knowledge present but not used at action time. The other 2
were explained (recall also dead).

## Where the raw zombies live — one precise pattern

All 6 raw zombies share the same signature:

- **Chain:** direct → paraphrase (6/12 in that chain; 0/12 in each of
  the other three chains).
- **Dead value:** v2 in all 6 — never v1. The reader never fell back to
  the oldest value; it fell back to the last clearly-marked update.
- **Kind:** price 3, schedule 2, rule 1, address 0.
- **Proximity:** dead_old 2/12, dead_recent 3/12, none 1/12, live_near
  0/12. The one none-cell zombie (upd-011) shows the re-mention is not
  required: the weak final update alone is enough.

The mechanism, on the evidence: in chain A the final update arrives as
a paraphrase — "Someone mentioned in passing that things have changed
for {entity}; these days the {attribute} is {v3}, not what it used to
be" — with no "Update:" marker and no supersession verb, buried in a
20k-token history. The reader misses that final update and acts on the
previous clearly-marked direct update (v2). Paraphrase as the *first*
update (chain B, followed by a tool_result final update) produced 0
zombies, so the finding is about weak phrasing **at the final
position**, not paraphrase in isolation — the design varies style and
position together, and the claim is stated at that level.

## Store arms: same story as v1, stronger

- **Retrieval 72.9% (35/48)** — and the reader used the retrieved chunk
  faithfully in 48/48 action probes (answers match the pre-recorded
  retriever choices exactly). Tie split, as the protocol requires:
  **12 of the 35 dead choices were index-order ties** (margin < 0.02,
  earliest chunk wins), **23 were clear TF-IDF wins for the v1 plant
  chunk** — the canonical "Record:" phrasing outscores the update
  phrasings on the query even without the tie-break. So the retrieval
  rate is not an artifact of the tie rule alone: 47.9% dead even
  counting only clear wins. A production embedding retriever remains a
  further step; this proxy is not claimed to be one.
- **Versioned 6.3% (3/48, all v2)** — exactly the reference store's
  pre-run distribution (45 current, 3 dead_v2); the reader added no
  error of its own.

## Guards

- Ceiling guard: **not fired** — raw 12.5%, not 0%.
- Floor guard: **not fired** — raw correct 87.5%, far above 50%.
- K1 (max arm < 5%): not fired. K2 (min arm > 20% with pure share
  < 10%): not fired (min arm 6.3%).

## Decision rule outcome

**The original reader thesis is alive.** The next decision is
publication / repo, not another pilot — unless the author requests a
replication first (a different model, or a paraphrase-final-only
replication at larger n, would both be fresh decisions with their own
caps).

## Limits (stated, not buried)

- One model, one contributor-tier id, synthetic transcripts, exact-value
  instruction. The 12.5% is a rate for this model class at this scale
  and rendering, not a universal constant.
- The chain-A effect is one paraphrase template at one position; other
  weak phrasings may behave differently.
- Retrieval is a TF-IDF proxy; an embedding index could rank versions
  differently (though the clear-win majority suggests the direction is
  not purely a tie artifact).
- Scores in `results/pilot_scores_v2.json`; raw responses in
  `responses_v2.jsonl`; retrieval choices with margins in
  `retrieval_choices_v2.jsonl`.
