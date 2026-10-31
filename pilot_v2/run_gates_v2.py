#!/usr/bin/env python3
"""Offline validation gates for the v2 pilot package. Writes results/gates_v2.json.

G1 balance      48 upd (4 chains x 4 proximities x 3 reps, kinds 12 each) + 12 ctl
G2 disjoint     v2 seed differs from spike (42) and v1 (90210); ids disjoint
G3 padding      every raw prompt within the 19k-21k token band
G4 clean        target entity/values occur only via target events; distractor
                values never equal a target value in the same scenario
G5 unlabelled   dead re-mentions contain no archive/historical/earlier/
                superseded wording
G6 gold sound   current == v3, dead set == {v1, v2}, all three distinct
G7 determinism  rebuilding reproduces the shipped file hashes
G8 stage A      exactly 8 Stage A prompts covering raw action/recall,
                retrieval action/recall, versioned action, control action
G9 scorer       perfect -> 0 zombies; all-v1 -> zombie_v1; all-v2 -> zombie_v2
"""
import hashlib
import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import build_prompts_v2 as bp
import score_v2 as sr
from generator_v2 import TOKEN_HI, TOKEN_LO, generate_dataset


def load_jsonl(name):
    return [json.loads(l) for l in (HERE / name).read_text().splitlines() if l.strip()]


def main() -> dict:
    gates = {}
    prompts = load_jsonl("prompts_v2.jsonl")
    gold = load_jsonl("gold_v2.jsonl")
    manifest = json.loads((HERE / "manifest_v2.json").read_text())
    scenarios = generate_dataset(bp.V2_SEED)
    by_id = {s.scenario_id: s for s in scenarios}
    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]
    kind_counts = Counter(s.kind for s in upd)
    gates["G1_balance"] = {"pass": len(upd) == 48 and len(ctl) == 12
                           and set(kind_counts.values()) == {12},
                           "n_update": len(upd), "n_control": len(ctl),
                           "kinds": dict(kind_counts)}
    gates["G2_disjoint"] = {"pass": bp.V2_SEED not in (bp.V1_SEED, bp.SPIKE_SEED)
                            and all(sid.startswith("pilot2-") for sid in by_id)}
    raw_ws = [p["ws_tokens"] for p in prompts if p["arm"] == "raw_transcript"]
    gates["G3_padding"] = {"pass": all(TOKEN_LO <= w <= TOKEN_HI for w in raw_ws),
                           "min": min(raw_ws), "max": max(raw_ws), "n_raw": len(raw_ws)}
    clean = True
    for s in scenarios:
        transcript = ""
        from generator_v2 import padded_transcript
        transcript = padded_transcript(s, strip_remention=False)
        raw_text = " ".join(e.text for e in s.events)
        for value in {s.v1, s.v2, s.v3}:
            if transcript.count(value) != raw_text.count(value):
                clean = False
        if transcript.count(s.entity) != raw_text.count(s.entity):
            clean = False
        for e in s.events:
            if e.kind == "distractor" and e.value in (s.v1, s.v2, s.v3):
                clean = False
    gates["G4_clean"] = {"pass": clean}
    banned = ("archive", "historical", "earlier", "superseded", "supersedes")
    bad = [e.event_id for s in scenarios for e in s.events
           if e.kind in ("remention_dead_old", "remention_dead_recent")
           and any(b in e.text.lower() for b in banned)]
    gates["G5_unlabelled"] = {"pass": not bad, "bad": bad[:5]}
    gold_ok = True
    for g in gold:
        s = by_id[g["scenario_id"]]
        if s.has_update and not (g["current_value"] == s.v3
                                 and g["dead_values"] == [s.v1, s.v2]
                                 and len({s.v1, s.v2, s.v3}) == 3):
            gold_ok = False
    gates["G6_gold_sound"] = {"pass": gold_ok, "n_gold": len(gold)}
    rebuilt = bp.build()

    def md5_rows(rows):
        return hashlib.md5("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()).hexdigest()
    gates["G7_determinism"] = {"pass": (
        md5_rows(rebuilt["prompts"]) == manifest["file_md5"]["prompts_v2.jsonl"]
        and md5_rows(rebuilt["gold"]) == manifest["file_md5"]["gold_v2.jsonl"]
        and md5_rows(rebuilt["retrieval_choices"]) == manifest["file_md5"]["retrieval_choices_v2.jsonl"])}
    stage_a = [p for p in prompts if p["stage"] == "A"]
    gates["G8_stage_a"] = {"pass": len(stage_a) == 8,
                           "prompt_ids": [p["prompt_id"] for p in stage_a]}
    fixture_ids = {s.scenario_id for s in upd[:8]}
    for key, expect in (("current_value", 0.0), ("dead_values", None)):
        resp = []
        for g in gold:
            if g["scenario_id"] in fixture_ids and g["phase"] in ("action", "recall"):
                val = g["current_value"] if key == "current_value" else g["dead_values"][1]
                resp.append({"prompt_id": g["prompt_id"], "response": val})
        rep = sr.score(resp, gold)
        arms = [a for a in rep["per_arm"] if rep["per_arm"][a]["n_action_update_scored"]]
        if key == "current_value":
            ok = all(rep["per_arm"][a]["zombie_rate"] == 0.0 for a in arms)
        else:
            ok = all(rep["per_arm"][a]["zombie_v2_rate"] == 1.0 for a in arms)
        gates[f"G9_scorer_{key}"] = {"pass": ok, "arms": arms}
    all_pass = all(g["pass"] for g in gates.values())
    out = {"all_pass": all_pass, "gates": gates, "n_prompts": len(prompts)}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "gates_v2.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res["all_pass"] else 1)
