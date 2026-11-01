"""Stage R: embed chunks + queries, retrieve, build reader prompts.

This is the experiment's first stage. It is NOT run as part of the
0 package build; it runs only under an approved proposal, because the
API backend spends money and the local backend downloads a model.

Inputs: chunks_emb.jsonl, queries_emb.jsonl, gold_emb.jsonl.
Outputs:
  retrieval_choices_emb.jsonl -- per probe: prompt_id, scenario_id,
      phase, chosen_event_id, chosen_value, score, second_score,
      margin, tie, backend, model, plus the gold values needed to
      classify the choice without joining files (current_value,
      dead_values, gold_status: current / dead_v1 / dead_v2 / other /
      control).
  prompts_emb.jsonl -- reader prompts in exactly v2's retrieval format:
      ANSWER_INSTRUCTION + "Memory (retrieved record):\\n" + chunk text
      + task. Rows carry stage A/B (see mark_stages).

Cost enforcement (API backend only): projected tokens are the manifest
upper bound (ws tokens x 1.4). Projected cost = upper tokens x
EMB_API_RATE_PER_M / 1e6. If it exceeds --cap, the script refuses
before any call. Local and stub backends spend 0 and ignore the cap.

Stage A marking (for the reader stage's calibration run): 8 prompts
chosen to span the outcome space, in this priority order:
  2 dead_v1 choices, 2 dead_v2 choices, 2 current choices,
  1 control, 1 tie (prefer a tie among dead choices).
Any category that is empty is skipped and the shortfall is filled from
the remaining prompts in file order. The selection is deterministic
given the choices file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pilot_v2"))

from build_prompts_v2 import ANSWER_INSTRUCTION  # noqa: E402
from embedder import embed_texts  # noqa: E402
from generator_v2 import ws_tokens  # noqa: E402
from retriever_emb import retrieve  # noqa: E402

DEFAULT_CAP = 0.05


def mark_stages(prompt_rows, choices):
    """Mark 8 stage-A rows spanning the outcome space (see module doc).

    prompt_rows: list of prompt dicts (with prompt_id). choices: dict
    prompt_id -> choice dict with gold_status and tie. Returns the same
    rows with a 'stage' field added ('A' or 'B').
    """
    by_id = choices
    wanted = []
    pools = {
        "dead_v1": [r for r in prompt_rows
                    if by_id[r["prompt_id"]]["gold_status"] == "dead_v1"],
        "dead_v2": [r for r in prompt_rows
                    if by_id[r["prompt_id"]]["gold_status"] == "dead_v2"],
        "current": [r for r in prompt_rows
                    if by_id[r["prompt_id"]]["gold_status"] == "current"],
        "control": [r for r in prompt_rows
                    if by_id[r["prompt_id"]]["gold_status"] == "control"],
    }
    tie_dead = [r for r in prompt_rows
                if by_id[r["prompt_id"]]["tie"]
                and by_id[r["prompt_id"]]["gold_status"] in ("dead_v1", "dead_v2")]
    for key, n in (("dead_v1", 2), ("dead_v2", 2), ("current", 2),
                   ("control", 1)):
        wanted.extend(pools[key][:n])
    wanted.extend(tie_dead[:1])
    picked = set()
    for r in wanted:
        picked.add(r["prompt_id"])
    for r in prompt_rows:  # fill any shortfall in file order
        if len(picked) >= 8:
            break
        picked.add(r["prompt_id"])
    for r in prompt_rows:
        r["stage"] = "A" if r["prompt_id"] in picked else "B"
    return prompt_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["stub", "local", "api"],
                    required=True)
    ap.add_argument("--cap", type=float, default=DEFAULT_CAP)
    args = ap.parse_args()

    manifest = json.load(open(os.path.join(HERE, "manifest_emb.json")))
    chunks = [json.loads(l) for l in
              open(os.path.join(HERE, "chunks_emb.jsonl"))]
    queries = [json.loads(l) for l in
               open(os.path.join(HERE, "queries_emb.jsonl"))]
    gold = {}
    for line in open(os.path.join(HERE, "gold_emb.jsonl")):
        row = json.loads(line)
        gold[row["prompt_id"]] = row

    if args.backend == "api":
        rate = os.environ.get("EMB_API_RATE_PER_M")
        if rate is None:
            raise RuntimeError(
                "API backend needs EMB_API_RATE_PER_M (dollars per "
                "million tokens) so the cap can be checked before "
                "any call.")
        projected = manifest["upper_token_bound_x1_4"] * float(rate) / 1e6
        print(f"projected embedding cost: {projected:.4f} "
              f"(cap {args.cap:.2f})")
        if projected > args.cap:
            raise RuntimeError(
                f"projected cost {projected:.4f} exceeds cap "
                f"{args.cap:.2f}; refusing to call the API.")
    else:
        print(f"backend {args.backend}: 0, cap not applicable")

    chunk_by_scenario = {}
    for c in chunks:
        chunk_by_scenario.setdefault(c["scenario_id"], []).append(c)

    # Embed all chunk texts, then all query texts, in file order.
    chunk_texts = [c["text"] for c in chunks]
    chunk_vecs = embed_texts(chunk_texts, args.backend)
    chunk_vec_by_id = {c["event_id"]: v
                       for c, v in zip(chunks, chunk_vecs)}
    query_vecs = embed_texts([q["task"] for q in queries], args.backend)

    model = (os.environ.get("EMB_LOCAL_MODEL", "all-MiniLM-L6-v2")
             if args.backend == "local" else
             os.environ.get("EMB_API_MODEL", "text-embedding-3-small")
             if args.backend == "api" else "stub")
    choices = []
    prompts = []
    for q, qvec in zip(queries, query_vecs):
        sc_chunks = chunk_by_scenario[q["scenario_id"]]
        res = retrieve([c["event_id"] for c in sc_chunks],
                       [chunk_vec_by_id[c["event_id"]] for c in sc_chunks],
                       qvec)
        chosen = next(c for c in sc_chunks
                      if c["event_id"] == res["chosen"])
        g = gold[q["prompt_id"]]
        # Classify the choice against the gold values, not the choice
        # itself: current / dead_v1 / dead_v2 / other (a distractor
        # entity's value) / control. Gold dead_values are [v1, v2].
        if not g["has_update"]:
            status = "control"
        elif chosen["value"] == g["current_value"]:
            status = "current"
        elif chosen["value"] == g["dead_values"][0]:
            status = "dead_v1"
        elif chosen["value"] == g["dead_values"][1]:
            status = "dead_v2"
        else:
            status = "other"
        choice = {
            "prompt_id": q["prompt_id"],
            "scenario_id": q["scenario_id"], "phase": q["phase"],
            "chosen_event_id": res["chosen"],
            "chosen_value": chosen["value"],
            "score": res["score"], "second_score": res["second_score"],
            "margin": res["margin"], "tie": res["tie"],
            "backend": args.backend, "model": model,
            "current_value": g["current_value"],
            "dead_values": g["dead_values"],
            "gold_status": status,
        }
        choices.append(choice)
        prompts.append({
            "prompt_id": q["prompt_id"],
            "scenario_id": q["scenario_id"], "arm": "retrieval",
            "phase": q["phase"], "kind": g["kind"],
            "chain": g.get("chain"), "proximity": g.get("proximity"),
            "prompt": (ANSWER_INSTRUCTION + "\n\nMemory (retrieved "
                       "record):\n" + chosen["text"] + "\n\nTask: "
                       + q["task"]),
            "ws_tokens": ws_tokens(chosen["text"]) + ws_tokens(q["task"]),
        })
    prompts = mark_stages(prompts, {c["prompt_id"]: c for c in choices})

    with open(os.path.join(HERE, "retrieval_choices_emb.jsonl"), "w") as f:
        for c in choices:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    with open(os.path.join(HERE, "prompts_emb.jsonl"), "w") as f:
        for p in prompts:
            f.write(json.dumps(p, sort_keys=True) + "\n")
    n_dead = sum(1 for c in choices
                 if c["gold_status"] in ("dead_v1", "dead_v2"))
    n_tie = sum(1 for c in choices if c["tie"])
    print(f"choices: {len(choices)}; dead choices: {n_dead}; "
          f"ties: {n_tie}; stage A: "
          f"{sum(1 for p in prompts if p['stage'] == 'A')}")
    print("wrote retrieval_choices_emb.jsonl and prompts_emb.jsonl")


if __name__ == "__main__":
    main()
