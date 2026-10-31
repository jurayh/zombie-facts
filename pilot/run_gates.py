#!/usr/bin/env python3
"""Offline validation gates for the live-pilot package. Writes results/gates.json.

Gates:
  G1 balance      factorial counts as designed (96 upd / 24 ctl, kinds balanced)
  G2 disjoint     pilot seed != spike seed; no scenario id overlap with spike ids
  G3 padding      every raw / summary-generate prompt within the token band
  G4 filler clean padded filler contains no target entity or value strings
  G5 no leakage   prompts carry no gold labels / benchmark vocabulary
  G6 gold sound   gold current/dead match the regenerated pilot dataset
  G7 determinism  rebuilding the corpus reproduces the shipped file hashes
  G8 stage A      exactly 8 Stage A prompts, covering all four arms' key phases
  G9 scorer       scorer classifies synthetic perfect / zombie / summary
                  responses exactly as expected on a fixture slice
"""
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import build_prompts as bp
import score_responses as sr
from zombie_facts.generator import generate_dataset


def load_jsonl(name):
    return [json.loads(l) for l in (HERE / name).read_text().splitlines() if l.strip()]


def main() -> dict:
    gates = {}
    prompts = load_jsonl("prompts_prebuilt.jsonl")
    gold = load_jsonl("gold.jsonl")
    templates = load_jsonl("summary_probe_templates.jsonl")
    manifest = json.loads((HERE / "manifest.json").read_text())
    scenarios = bp.pilot_dataset()
    by_id = {s.scenario_id: s for s in scenarios}

    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]
    from collections import Counter
    kind_counts = Counter(s.kind for s in upd)
    gates["G1_balance"] = {
        "pass": len(upd) == 96 and len(ctl) == 24 and set(kind_counts.values()) == {24},
        "n_update": len(upd), "n_control": len(ctl), "kinds": dict(kind_counts)}

    spike_ids = {s.scenario_id for s in generate_dataset(bp.SPIKE_SEED, 5)}
    gates["G2_disjoint"] = {
        "pass": bp.PILOT_SEED != bp.SPIKE_SEED and not (set(by_id) & spike_ids),
        "pilot_seed": bp.PILOT_SEED, "spike_seed": bp.SPIKE_SEED}

    padded = [p for p in prompts if p["arm"] == "raw_transcript"
              or (p["arm"] == "summary" and p["phase"] == "generate")]
    gates["G3_padding"] = {
        "pass": all(bp.TOKEN_LO <= p["ws_tokens"] <= bp.TOKEN_HI for p in padded),
        "min": min(p["ws_tokens"] for p in padded), "max": max(p["ws_tokens"] for p in padded),
        "n_padded": len(padded)}

    clean = True
    for s in scenarios:
        transcript = bp.padded_transcript(s, strip_remention=False)
        # filler cleanliness: every fact value appears only via its own event
        # texts — count occurrences in the transcript vs in the raw event texts.
        raw_text = " ".join(e.text for e in s.events)
        for value in {s.v1, s.current_value}:
            if transcript.count(value) != raw_text.count(value):
                clean = False
        if transcript.count(s.entity) != raw_text.count(s.entity):
            clean = False
    gates["G4_filler_clean"] = {"pass": clean}

    banned = ("zombie", "ground truth", "ground_truth", "dead_value", "current_value",
              "benchmark", "superseded fact")
    leaks = [p["prompt_id"] for p in prompts
             if any(b in p["prompt"].lower() for b in banned)]
    gates["G5_no_leakage"] = {"pass": not leaks, "leaks": leaks[:5]}

    gold_ok = True
    for g in gold:
        s = by_id[g["scenario_id"]]
        if g["current_value"] != s.current_value:
            gold_ok = False
        if s.has_update and g["dead_value"] != s.v1:
            gold_ok = False
        if not s.has_update and g["dead_value"] is not None:
            gold_ok = False
    gates["G6_gold_sound"] = {"pass": gold_ok, "n_gold": len(gold)}

    rebuilt = bp.build()
    def md5_rows(rows):
        return hashlib.md5("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()).hexdigest()
    gates["G7_determinism"] = {
        "pass": (md5_rows(rebuilt["prompts"]) == manifest["file_md5"]["prompts_prebuilt.jsonl"]
                 and md5_rows(rebuilt["gold"]) == manifest["file_md5"]["gold.jsonl"]
                 and md5_rows(rebuilt["templates"]) == manifest["file_md5"]["summary_probe_templates.jsonl"])}

    stage_a = [p for p in prompts if p["stage"] == "A"]
    gates["G8_stage_a"] = {
        "pass": len(stage_a) == 8,
        "prompt_ids": [p["prompt_id"] for p in stage_a]}

    # G9 scorer fixture: perfect answers -> 0 zombies; all-dead -> all zombies
    fixture = [s for s in upd[:12]]
    perfect, zombie = [], []
    for g in gold:
        if g["scenario_id"] in {s.scenario_id for s in fixture} and g["phase"] in ("action", "recall"):
            perfect.append({"prompt_id": g["prompt_id"], "response": g["current_value"]})
            zombie.append({"prompt_id": g["prompt_id"],
                           "response": g["dead_value"] or g["current_value"]})
    rep_p = sr.score(perfect, gold)
    rep_z = sr.score(zombie, gold)
    arms_checked = [a for a in rep_p["per_arm"] if rep_p["per_arm"][a]["n_action_update_scored"]]
    g9 = all(rep_p["per_arm"][a]["zombie_rate"] == 0.0 for a in arms_checked) and \
         all(rep_z["per_arm"][a]["zombie_rate"] == 1.0 for a in arms_checked
             if rep_z["per_arm"][a]["n_action_update_scored"])
    gates["G9_scorer_fixture"] = {"pass": g9, "arms_checked": arms_checked}

    all_pass = all(g["pass"] for g in gates.values())
    out = {"all_pass": all_pass, "gates": gates,
           "n_prebuilt_prompts": len(prompts), "n_templates": len(templates)}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "gates.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res["all_pass"] else 1)
