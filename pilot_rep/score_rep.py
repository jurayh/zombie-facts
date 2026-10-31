#!/usr/bin/env python3
"""Score v2 pilot responses against gold_rep.jsonl. Offline.

Classification for action/recall probes on update scenarios:
  correct  == current value (v3)
  zombie_v2  == v2 (most recent dead value)
  zombie_v1  == v1 (oldest dead value)
  other    anything else / no answer
Zombie rate = zombie_v1 + zombie_v2. Pure zombies = action zombie AND
paired recall correct. Truncated responses are excluded and counted
separately (protocol rule). Spend is priced at contributor rates when
token fields are present.
"""
import argparse
import json
import pathlib
import re
from collections import defaultdict

HERE = pathlib.Path(__file__).parent
RATES = {"input_per_m": 0.10, "output_per_m": 0.20}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()


def classify(response: str, gold: dict) -> str:
    r = norm(response)
    if r == norm(gold["current_value"]):
        return "correct"
    if gold["dead_values"]:
        if r == norm(gold["dead_values"][1]):
            return "zombie_v2"
        if r == norm(gold["dead_values"][0]):
            return "zombie_v1"
    if norm(gold["current_value"]) in r:
        return "correct"
    return "other"


def score(responses: list[dict], gold_rows: list[dict]) -> dict:
    gold = {g["prompt_id"]: g for g in gold_rows}
    results: dict[str, str] = {}
    spend_in = spend_out = n_trunc = 0
    for row in responses:
        g = gold.get(row["prompt_id"])
        if g is None:
            continue
        spend_in += row.get("input_tokens", 0) or 0
        spend_out += row.get("output_tokens", 0) or 0
        if row.get("truncated"):
            n_trunc += 1
            continue
        results[row["prompt_id"]] = classify(row.get("response", ""), g)

    def rate(pred, d):
        return round(sum(1 for v in d.values() if pred(v)) / len(d), 4) if d else None

    per_arm: dict[str, dict] = {}
    for arm in sorted({g["arm"] for g in gold_rows}):
        upd_action = {pid: r for pid, r in results.items()
                      if gold[pid]["arm"] == arm and gold[pid]["phase"] == "action"
                      and gold[pid]["has_update"]}
        ctl_action = {pid: r for pid, r in results.items()
                      if gold[pid]["arm"] == arm and gold[pid]["phase"] == "action"
                      and not gold[pid]["has_update"]}
        pure = sum(1 for pid, r in upd_action.items()
                   if r in ("zombie_v1", "zombie_v2")
                   and results.get(pid.replace("__action", "__recall")) == "correct")
        entry = {
            "n_action_update_scored": len(upd_action),
            "zombie_rate": rate(lambda v: v in ("zombie_v1", "zombie_v2"), upd_action),
            "zombie_v1_rate": rate(lambda v: v == "zombie_v1", upd_action),
            "zombie_v2_rate": rate(lambda v: v == "zombie_v2", upd_action),
            "correct_rate": rate(lambda v: v == "correct", upd_action),
            "other_rate": rate(lambda v: v == "other", upd_action),
            "pure_zombie_rate": round(pure / len(upd_action), 4) if upd_action else None,
            "n_control_scored": len(ctl_action),
            "control_accuracy": rate(lambda v: v == "correct", ctl_action),
        }
        # Breakdowns for the raw arm (primary contrast).
        if arm == "raw_transcript":
            for key in ("proximity", "chain"):
                groups: dict[str, list] = defaultdict(list)
                for pid, r in upd_action.items():
                    groups[str(gold[pid][key])].append(r)
                entry[f"by_{key}"] = {
                    k: {"n": len(v), "zombie_rate": round(
                        sum(1 for x in v if x in ("zombie_v1", "zombie_v2")) / len(v), 4),
                        "zombie_v1_rate": round(v.count("zombie_v1") / len(v), 4),
                        "zombie_v2_rate": round(v.count("zombie_v2") / len(v), 4)}
                    for k, v in sorted(groups.items())}
        per_arm[arm] = entry

    report = {"per_arm": per_arm, "n_responses_scored": len(results),
              "n_truncated_excluded": n_trunc}
    if spend_in or spend_out:
        report["tokens"] = {"input": spend_in, "output": spend_out}
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("responses", nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args()
    gold_rows = [json.loads(l) for l in (HERE / "gold_rep.jsonl").read_text().splitlines() if l.strip()]
    responses = []
    for path in args.responses:
        responses += [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    report = score(responses, gold_rows)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n")
    print(text)
