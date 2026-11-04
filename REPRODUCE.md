# Reproduce

## Offline (no model calls, no key)

```bash
python3 run_spike.py                    # scripted core, byte-identical results
python3 -m unittest discover -s tests   # 27 tests: core + v1/v2/rep gates

# Rebuild each live corpus deterministically (byte-identical to the
# manifests' md5 hashes) and rerun its gates:
python3 pilot/build_prompts.py
python3 pilot/run_gates.py
python3 pilot_v2/build_prompts_v2.py
python3 pilot_v2/run_gates_v2.py
python3 pilot_rep/build_prompts_rep.py
python3 pilot_rep/run_gates_rep.py
python3 pilot_emb/build_inventory_emb.py   # rebuilds chunks/queries/gold, byte-identical to the manifest hash
python3 pilot_emb/run_gates_emb.py        # 15 gates, stub backend only, no downloads
python3 -m unittest discover -s pilot_emb/tests  # 10 tests
```

The large prompt corpora (`prompts_*.jsonl`, ~12 MB each) and raw model
responses are intentionally not shipped: every corpus rebuilds
byte-identically from its generator, and the manifests record the
hashes to check against. Gold files and score files are shipped.

## Live rerun (needs your own key and your own cap)

The runners were adapted for public use: the author's internal
credential helper was replaced with a plain `META_MODEL_API_KEY`
environment variable. Model, endpoint, rates, caps, prompts, and
scoring are otherwise unchanged.

```bash
export META_MODEL_API_KEY=...   # Meta Model API key, contributor tier recommended
python3 pilot_v2/run_pilot_v2.py --stage A    # 8 calibration calls
# Check the projection against your cap, then:
python3 pilot_v2/run_pilot_v2.py --stage B
python3 pilot_v2/score_v2.py pilot_v2/responses_v2.jsonl
```

## Embedding pilot (pilot_emb/)

Stage R (retrieval) runs locally with no key and no money cost:

```bash
python3 -m venv pilot_emb/.venv
pilot_emb/.venv/bin/pip install sentence-transformers --extra-index-url https://download.pytorch.org/whl/cpu
pilot_emb/.venv/bin/python pilot_emb/run_retrieval_emb.py --backend local
```

The first run downloads all-MiniLM-L6-v2 (about 90 MB) from the
Hugging Face hub; later runs reuse the cache. Stage R writes
`retrieval_choices_emb.jsonl` and `prompts_emb.jsonl` (stage A
marked). It also writes `retrieval_rankings_emb.jsonl`
(the full per-probe ranking). The tie-epsilon counterfactual runs
offline from those files:

```bash
python3 pilot_emb/counterfactual_epsilon.py
```

It verifies 0.02 reproduces the as-run choices, then prints the
dead rate at each epsilon and writes
`pilot_emb/results/counterfactual_epsilon.json`. The hosted-API backend (`--backend api`) is an alternative
for the same stage: it takes `EMB_API_URL`, `EMB_API_MODEL`,
`EMB_API_KEY`, and `EMB_API_RATE_PER_M`, and refuses to call the API
if the projected cost from the confirmed rate exceeds its cap.

Reader stage (needs your own key and your own cap):

```bash
export META_MODEL_API_KEY=<redacted>
python3 pilot_emb/run_reader_emb.py --stage A
# Check the projection against your cap, then:
python3 pilot_emb/run_reader_emb.py --stage B
python3 pilot_emb/score_emb.py pilot_emb/responses_emb.jsonl
```

The shipped reader was adapted the same way as the other runners: it
reads a plain `META_MODEL_API_KEY` environment variable. The
`.venv` directory is local only and is never shipped.


Each runner enforces its cap itself: it tracks billed tokens from every
response's usage block and refuses to start a wave whose conservative
estimate would cross the cap. The caps in the shipped runners
are the caps from the original runs — set your own before rerunning. Nothing here will spend money without the env var
set and the cap in the runner file.

Scale of the original runs, for planning: v1 984 calls at ~2k
tokens, v2 324 calls at ~20k tokens, replication 104 calls at ~20k
tokens, all on contributor-tier pricing. Standard-tier pricing would be roughly 10-20x.
The embedding pilot adds 108 reader calls on short retrieval prompts,
plus a local embedding stage (823 chunks + 108 queries) with no money
cost.
