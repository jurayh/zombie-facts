#!/usr/bin/env python3
"""Build the Zombie Facts v2 (hard-regime) live-pilot corpus offline.

Arms: raw_transcript, retrieval (TF-IDF, see retriever_v2.py), versioned
(reference registration: each update registers with the v1 style-dependent
probability table, applied independently to both chain updates; the current
record is the last registered value).
The summary arm is excluded from v2 by design: v1 live showed it clean
(0% zombie, 100% lenient correct), and model-written summaries over 20k
tokens would dominate the run's cost without testing the primary question
(reader susceptibility). It is a documented deferral, not an oversight.

Outputs (this directory): prompts_v2.jsonl, gold_v2.jsonl,
retrieval_choices_v2.jsonl (chunk chosen + margin per retrieval prompt),
manifest_v2.json.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

from generator_v2 import CHAINS, KINDS, PROXIMITIES, generate_dataset, padded_transcript, ws_tokens
from retriever_v2 import retrieve

V2_SEED = 777013
V1_SEED = 90210
SPIKE_SEED = 42

ANSWER_INSTRUCTION = (
    "You are an agent with access to memory from earlier sessions. Use only the "
    "memory below. Reply with the exact value only, and nothing else."
)
# Reference versioned-store registration probabilities (same table as v1).
VERSIONED_EXTRACT = {"direct": 1.00, "paraphrase": 0.85, "document": 0.95, "tool_result": 0.70}


def _stable_unit(*parts: object) -> float:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16) / float(16**12)


def _versioned_current(scenario, seed: int) -> str:
    current = scenario.v1
    for i, upd in enumerate([e for e in scenario.events if e.kind == "update"]):
        if _stable_unit(seed, scenario.scenario_id, "versioned", upd.event_id) < VERSIONED_EXTRACT[upd.style]:
            current = upd.value
    return current


def build() -> dict:
    scenarios = generate_dataset(V2_SEED)
    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]

    prompts: list[dict] = []
    gold: list[dict] = []
    retrieval_choices: list[dict] = []

    def add(s, arm, phase, prompt, stage="B"):
        pid = f"{s.scenario_id}__{arm}__{phase}"
        prompts.append({"prompt_id": pid, "scenario_id": s.scenario_id, "arm": arm,
                        "phase": phase, "kind": s.kind,
                        "chain": list(s.chain) if s.has_update else None,
                        "proximity": s.proximity, "stage": stage,
                        "prompt": prompt, "ws_tokens": ws_tokens(prompt)})
        return pid

    def add_gold(s, arm, phase):
        gold.append({"prompt_id": f"{s.scenario_id}__{arm}__{phase}",
                     "scenario_id": s.scenario_id, "arm": arm, "phase": phase,
                     "kind": s.kind, "chain": list(s.chain) if s.has_update else None,
                     "proximity": s.proximity, "has_update": s.has_update,
                     "current_value": s.current_value,
                     "dead_values": s.dead_values if s.has_update else []})

    # Stage A picks: first dead_old (chain B), first dead_recent (chain A),
    # first live_near (chain C), first control.
    a_old = next(s for s in upd if s.proximity == "dead_old" and s.chain == CHAINS[1])
    a_recent = next(s for s in upd if s.proximity == "dead_recent" and s.chain == CHAINS[0])
    a_live = next(s for s in upd if s.proximity == "live_near" and s.chain == CHAINS[2])
    stage_a = {
        (a_old.scenario_id, "raw_transcript", "action"),
        (a_old.scenario_id, "raw_transcript", "recall"),
        (a_recent.scenario_id, "raw_transcript", "action"),
        (a_live.scenario_id, "raw_transcript", "action"),
        (a_old.scenario_id, "retrieval", "action"),
        (a_old.scenario_id, "versioned", "action"),
        (a_recent.scenario_id, "retrieval", "recall"),
        (ctl[0].scenario_id, "raw_transcript", "action"),
    }

    for s in scenarios:
        phases = ("action", "recall") if s.has_update else ("action",)
        for phase in phases:
            strip = phase == "recall"
            prompt = (f"{ANSWER_INSTRUCTION}\n\nMemory (session history):\n"
                      f"{padded_transcript(s, strip)}\n\nTask: "
                      f"{s.action_probe() if phase == 'action' else s.recall_probe()}")
            add(s, "raw_transcript", phase, prompt,
                "A" if (s.scenario_id, "raw_transcript", phase) in stage_a else "B")
            add_gold(s, "raw_transcript", phase)
        # retrieval + versioned artifacts (same artifact for action and recall;
        # the recall probe's stripped history is not re-retrieved, matching v1)
        fact_chunks = [e for e in s.events if e.fact_bearing]
        for phase in phases:
            task = s.action_probe() if phase == "action" else s.recall_probe()
            chunk, score, margin = retrieve(fact_chunks, task)
            prompt = (f"{ANSWER_INSTRUCTION}\n\nMemory (retrieved record):\n"
                      f"{chunk.text}\n\nTask: {task}")
            add(s, "retrieval", phase, prompt,
                "A" if (s.scenario_id, "retrieval", phase) in stage_a else "B")
            add_gold(s, "retrieval", phase)
            if phase == "action":
                retrieval_choices.append({
                    "scenario_id": s.scenario_id, "chosen_event_id": chunk.event_id,
                    "chosen_kind": chunk.kind, "chosen_value": chunk.value,
                    "score": round(score, 4), "margin": round(margin, 4),
                    "tie": margin < 0.02})
            current = _versioned_current(s, V2_SEED)
            prompt = (f"{ANSWER_INSTRUCTION}\n\nMemory (current record):\n"
                      f"{s.entity} — the {s.attribute} is {current}.\n\nTask: {task}")
            add(s, "versioned", phase, prompt,
                "A" if (s.scenario_id, "versioned", phase) in stage_a else "B")
            add_gold(s, "versioned", phase)

    raw_ws = [p["ws_tokens"] for p in prompts if p["arm"] == "raw_transcript"]
    total_ws = sum(p["ws_tokens"] for p in prompts)
    manifest = {
        "v2_seed": V2_SEED, "v1_seed": V1_SEED, "spike_seed": SPIKE_SEED,
        "n_scenarios": len(scenarios), "n_update_scenarios": len(upd),
        "n_control_scenarios": len(ctl), "n_prompts": len(prompts),
        "arms": ["raw_transcript", "retrieval", "versioned"],
        "prebuilt_ws_tokens_total": total_ws,
        "raw_prompt_ws_tokens_min": min(raw_ws), "raw_prompt_ws_tokens_max": max(raw_ws),
        "raw_prompt_ws_tokens_mean": round(sum(raw_ws) / len(raw_ws), 1),
        "bpe_upper_factor": 1.4,
        "model": "muse-spark-1.3-contributor",
        "output_caps": {"action": 1024, "recall": 1024},
        "expected_output_tokens_per_call": {"action": 500, "recall": 500},
        "stage_a_prompt_ids": sorted(p["prompt_id"] for p in prompts if p["stage"] == "A"),
    }
    return {"prompts": prompts, "gold": gold, "retrieval_choices": retrieval_choices,
            "manifest": manifest}


def _dump(name: str, rows: list[dict], outdir: pathlib.Path):
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    (outdir / name).write_text(text)
    return hashlib.md5(text.encode()).hexdigest()


if __name__ == "__main__":
    outdir = HERE
    built = build()
    hashes = {
        "prompts_v2.jsonl": _dump("prompts_v2.jsonl", built["prompts"], outdir),
        "gold_v2.jsonl": _dump("gold_v2.jsonl", built["gold"], outdir),
        "retrieval_choices_v2.jsonl": _dump("retrieval_choices_v2.jsonl",
                                            built["retrieval_choices"], outdir),
    }
    built["manifest"]["file_md5"] = hashes
    (outdir / "manifest_v2.json").write_text(
        json.dumps(built["manifest"], indent=2, sort_keys=True) + "\n")
    print(json.dumps(built["manifest"], indent=2, sort_keys=True))
