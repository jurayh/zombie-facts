#!/usr/bin/env python3
"""Build the Zombie Facts varied-phrasing replication corpus offline.

Raw arm only: the question is whether the reader misses a weakly phrased
final update, so only the raw transcript arm is probed. Retrieval and
versioned arms are out of scope for this replication (v2 already measured
them, and neither tests final-update phrasing).

Outputs (this directory): prompts_rep.jsonl, gold_rep.jsonl, manifest_rep.json.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

from generator_rep import FINAL_STYLES, REP_SEED, V1_SEED, V2_SEED, SPIKE_SEED, generate_dataset
from generator_v2 import TOKEN_HI, TOKEN_LO, padded_transcript, ws_tokens

ANSWER_INSTRUCTION = (
    "You are an agent with access to memory from earlier sessions. Use only the "
    "memory below. Reply with the exact value only, and nothing else."
)


def build() -> dict:
    scenarios = generate_dataset(REP_SEED)
    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]

    # Stage A (8): baseline action+recall, one novel weak action+recall,
    # direct-control action, one more novel weak action, control action,
    # one more novel weak action.
    by_final = {}
    for s in upd:
        by_final.setdefault(s.chain[1], []).append(s)
    stage_a = {
        (by_final["weak_baseline"][0].scenario_id, "action"),
        (by_final["weak_baseline"][0].scenario_id, "recall"),
        (by_final["weak_aside"][0].scenario_id, "action"),
        (by_final["weak_aside"][0].scenario_id, "recall"),
        (by_final["direct"][0].scenario_id, "action"),
        (by_final["weak_hearsay"][0].scenario_id, "action"),
        (by_final["weak_parenthetical"][0].scenario_id, "action"),
        (ctl[0].scenario_id, "action"),
    }

    prompts: list[dict] = []
    gold: list[dict] = []

    def add(s, phase, prompt, stage):
        prompts.append({"prompt_id": f"{s.scenario_id}__raw_transcript__{phase}",
                        "scenario_id": s.scenario_id, "arm": "raw_transcript",
                        "phase": phase, "kind": s.kind,
                        "chain": list(s.chain) if s.has_update else None,
                        "final_style": s.chain[1] if s.has_update else None,
                        "proximity": s.proximity, "stage": stage,
                        "prompt": prompt, "ws_tokens": ws_tokens(prompt)})

    def add_gold(s, phase):
        gold.append({"prompt_id": f"{s.scenario_id}__raw_transcript__{phase}",
                     "scenario_id": s.scenario_id, "arm": "raw_transcript",
                     "phase": phase, "kind": s.kind,
                     "chain": list(s.chain) if s.has_update else None,
                     "final_style": s.chain[1] if s.has_update else None,
                     "proximity": s.proximity, "has_update": s.has_update,
                     "current_value": s.current_value,
                     "dead_values": s.dead_values if s.has_update else []})

    for s in scenarios:
        phases = ("action", "recall") if s.has_update else ("action",)
        for phase in phases:
            strip = phase == "recall"
            prompt = (f"{ANSWER_INSTRUCTION}\n\nMemory (session history):\n"
                      f"{padded_transcript(s, strip)}\n\nTask: "
                      f"{s.action_probe() if phase == 'action' else s.recall_probe()}")
            add(s, phase, prompt,
                "A" if (s.scenario_id, phase) in stage_a else "B")
            add_gold(s, phase)

    raw_ws = [p["ws_tokens"] for p in prompts]
    manifest = {
        "rep_seed": REP_SEED, "v2_seed": V2_SEED, "v1_seed": V1_SEED, "spike_seed": SPIKE_SEED,
        "n_scenarios": len(scenarios), "n_update_scenarios": len(upd),
        "n_control_scenarios": len(ctl), "n_prompts": len(prompts),
        "arms": ["raw_transcript"], "final_styles": FINAL_STYLES,
        "prebuilt_ws_tokens_total": sum(raw_ws),
        "raw_prompt_ws_tokens_min": min(raw_ws), "raw_prompt_ws_tokens_max": max(raw_ws),
        "raw_prompt_ws_tokens_mean": round(sum(raw_ws) / len(raw_ws), 1),
        "bpe_upper_factor": 1.4,
        "model": "muse-spark-1.3-contributor",
        "output_caps": {"action": 1024, "recall": 1024},
        "expected_output_tokens_per_call": {"action": 500, "recall": 500},
        "stage_a_prompt_ids": sorted(p["prompt_id"] for p in prompts if p["stage"] == "A"),
    }
    return {"prompts": prompts, "gold": gold, "manifest": manifest}


def _dump(name: str, rows: list[dict], outdir: pathlib.Path):
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    (outdir / name).write_text(text)
    return hashlib.md5(text.encode()).hexdigest()


if __name__ == "__main__":
    built = build()
    hashes = {
        "prompts_rep.jsonl": _dump("prompts_rep.jsonl", built["prompts"], HERE),
        "gold_rep.jsonl": _dump("gold_rep.jsonl", built["gold"], HERE),
    }
    built["manifest"]["file_md5"] = hashes
    (HERE / "manifest_rep.json").write_text(
        json.dumps(built["manifest"], indent=2, sort_keys=True) + "\n")
    print(json.dumps(built["manifest"], indent=2, sort_keys=True))
