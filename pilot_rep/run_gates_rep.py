#!/usr/bin/env python3
"""Offline validation gates for the varied-phrasing replication package.
Writes results/gates_rep.json.

G1 balance      48 upd (6 finals x 4 kinds x 2 reps) + 8 ctl
G2 disjoint     rep seed differs from spike (42), v1 (90210), v2 (777013);
                ids disjoint (pilot3- prefix)
G3 padding      every prompt within the 19k-21k token band
G4 clean        target entity/values occur only via target events; distractor
                values never equal a target value in the same scenario
G5 weak         final-update texts contain no Update marker or supersession
                wording (update/replace/supersede/previous/archive/historical/
                earlier); direct control DOES carry the marker (negative control)
G6 gold sound   current == v3, dead set == {v1, v2}, all three distinct
G7 determinism  rebuilding reproduces the shipped file hashes
G8 stage A      exactly 8 Stage A prompts covering baseline action+recall,
                a novel weak action+recall, direct-control action, control
G9 scorer       perfect -> 0 zombies; all-v2 -> zombie_v2
"""
import hashlib
import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pilot_v2"))

import build_prompts_rep as bp
import score_rep as sr
from generator_rep import FINAL_STYLES, REP_SEED, SPIKE_SEED, V1_SEED, V2_SEED, generate_dataset
from generator_v2 import TOKEN_HI, TOKEN_LO, padded_transcript

BANNED = ("update", "replace", "supersede", "previous", "archive", "historical", "earlier")


def load_jsonl(name):
    return [json.loads(l) for l in (HERE / name).read_text().splitlines() if l.strip()]


def main() -> dict:
    gates = {}
    prompts = load_jsonl("prompts_rep.jsonl")
    gold = load_jsonl("gold_rep.jsonl")
    manifest = json.loads((HERE / "manifest_rep.json").read_text())
    scenarios = generate_dataset(REP_SEED)
    by_id = {s.scenario_id: s for s in scenarios}
    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]
    final_counts = Counter(s.chain[1] for s in upd)
    kind_counts = Counter(s.kind for s in upd)
    gates["G1_balance"] = {"pass": len(upd) == 48 and len(ctl) == 8
                           and set(final_counts.values()) == {8}
                           and set(kind_counts.values()) == {12},
                           "n_update": len(upd), "n_control": len(ctl),
                           "finals": dict(final_counts), "kinds": dict(kind_counts)}
    gates["G2_disjoint"] = {"pass": REP_SEED not in (V2_SEED, V1_SEED, SPIKE_SEED)
                            and all(sid.startswith("pilot3-") for sid in by_id)}
    raw_ws = [p["ws_tokens"] for p in prompts]
    gates["G3_padding"] = {"pass": all(TOKEN_LO <= w <= TOKEN_HI for w in raw_ws),
                           "min": min(raw_ws), "max": max(raw_ws), "n_prompts": len(raw_ws)}
    clean = True
    for s in scenarios:
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
    bad = []
    for s in upd:
        final_event = [e for e in s.events if e.kind == "update" and e.session == 4][0]
        text = final_event.text.lower()
        if s.chain[1] == "direct":
            if "update:" not in text:
                bad.append((s.scenario_id, "direct control missing marker"))
        elif any(b in text for b in BANNED):
            bad.append((s.scenario_id, final_event.text))
    gates["G5_weak"] = {"pass": not bad, "bad": bad[:5]}
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
        md5_rows(rebuilt["prompts"]) == manifest["file_md5"]["prompts_rep.jsonl"]
        and md5_rows(rebuilt["gold"]) == manifest["file_md5"]["gold_rep.jsonl"])}
    stage_a = [p for p in prompts if p["stage"] == "A"]
    gates["G8_stage_a"] = {"pass": len(stage_a) == 8,
                           "prompt_ids": [p["prompt_id"] for p in stage_a]}
    fixture_ids = {s.scenario_id for s in upd[:8]}
    for key in ("current_value", "dead_values"):
        resp = []
        for g in gold:
            if g["scenario_id"] in fixture_ids and g["phase"] in ("action", "recall"):
                val = g["current_value"] if key == "current_value" else g["dead_values"][1]
                resp.append({"prompt_id": g["prompt_id"], "response": val})
        rep = sr.score(resp, gold)
        entry = rep["per_arm"]["raw_transcript"]
        if key == "current_value":
            ok = entry["zombie_rate"] == 0.0
        else:
            ok = entry["zombie_v2_rate"] == 1.0
        gates[f"G9_scorer_{key}"] = {"pass": ok}
    all_pass = all(g["pass"] for g in gates.values())
    out = {"all_pass": all_pass, "gates": gates, "n_prompts": len(prompts)}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "gates_rep.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res["all_pass"] else 1)
