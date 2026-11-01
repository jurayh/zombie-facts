"""Build the embedding-retriever inventory from the v2 corpus.

This is NOT a new dataset. It reuses pilot_v2's corpus (seed 777013)
exactly: same scenarios, same fact-bearing chunks, same probe tasks,
same gold. The only new object is a retrieval arm whose ranking comes
from embeddings instead of TF-IDF, so the embedding zombie rate is
directly comparable to the TF-IDF 72.9%.

Outputs (all in this directory):
  chunks_emb.jsonl  -- one row per fact-bearing chunk: scenario_id,
                       event_id, session, kind, style, value, entity,
                       attribute, text.
  queries_emb.jsonl -- one row per retrieval probe: prompt_id,
                       scenario_id, phase (action/recall), task.
  gold_emb.jsonl    -- v2's retrieval gold rows, copied verbatim.
  manifest_emb.json -- counts, token totals, hashes, tie epsilon,
                       backend note.

Run: python3 build_inventory_emb.py
Deterministic: rebuilding produces byte-identical files.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pilot_v2"))

from generator_v2 import generate_dataset, ws_tokens  # noqa: E402

SEED = 777013
V2_DIR = os.path.join(os.path.dirname(HERE), "pilot_v2")


def _sha(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(open(p, "rb").read())
    return h.hexdigest()


def main():
    scenarios = generate_dataset(SEED)

    chunks = []
    for s in scenarios:
        for e in s.events:
            if not e.fact_bearing:
                continue
            chunks.append({
                "scenario_id": s.scenario_id, "event_id": e.event_id,
                "session": e.session, "kind": e.kind,
                "style": e.style, "value": e.value,
                "entity": e.entity, "attribute": e.attribute,
                "text": e.text,
            })

    queries = []
    for s in scenarios:
        queries.append({
            "prompt_id": f"{s.scenario_id}__retrieval__action",
            "scenario_id": s.scenario_id, "phase": "action",
            "task": s.action_probe(),
        })
        if s.has_update:
            queries.append({
                "prompt_id": f"{s.scenario_id}__retrieval__recall",
                "scenario_id": s.scenario_id, "phase": "recall",
                "task": s.recall_probe(),
            })

    gold = [json.loads(l) for l in open(os.path.join(V2_DIR, "gold_v2.jsonl"))
            if json.loads(l)["arm"] == "retrieval"]

    chunk_path = os.path.join(HERE, "chunks_emb.jsonl")
    query_path = os.path.join(HERE, "queries_emb.jsonl")
    gold_path = os.path.join(HERE, "gold_emb.jsonl")
    with open(chunk_path, "w") as f:
        for row in chunks:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with open(query_path, "w") as f:
        for row in queries:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    with open(gold_path, "w") as f:
        for row in gold:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    chunk_tokens = sum(ws_tokens(c["text"]) for c in chunks)
    query_tokens = sum(ws_tokens(q["task"]) for q in queries)
    manifest = {
        "seed": SEED,
        "source": "pilot_v2 corpus, seed 777013, reused exactly",
        "n_scenarios": len(scenarios),
        "n_update_scenarios": sum(1 for s in scenarios if s.has_update),
        "n_control_scenarios": sum(1 for s in scenarios if not s.has_update),
        "n_chunks": len(chunks),
        "n_queries": len(queries),
        "n_gold_rows": len(gold),
        "chunk_ws_tokens": chunk_tokens,
        "query_ws_tokens": query_tokens,
        "total_ws_tokens": chunk_tokens + query_tokens,
        "upper_token_bound_x1_4": round((chunk_tokens + query_tokens) * 1.4),
        "tie_epsilon": 0.02,
        "files_sha256": _sha([chunk_path, query_path, gold_path]),
    }
    with open(os.path.join(HERE, "manifest_emb.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
