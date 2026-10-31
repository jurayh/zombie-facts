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

Each runner enforces its cap itself: it tracks billed tokens from every
response's usage block and refuses to start a wave whose conservative
estimate would cross the cap. The caps in the shipped runners
The caps in the shipped runners are the caps from the original runs — set your
own before rerunning. Nothing here will spend money without the env var
set and the cap in the runner file.

Scale of the original runs, for planning: v1 984 calls at ~2k
tokens, v2 324 calls at ~20k tokens, replication 104 calls at ~20k
tokens, all on contributor-tier pricing. Standard-tier pricing would be roughly 10-20x.
