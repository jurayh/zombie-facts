#!/usr/bin/env python3
"""Score live-pilot responses against gold.jsonl. Offline.

Input: one or more response files, JSONL rows:
    {"prompt_id": "...", "response": "..."}
    (optional: "input_tokens", "output_tokens" for spend accounting)

Output: a JSON report (stdout or --out) with, per arm:
  action zombie / correct / other rates, paired-recall attribution
  (pure zombies = action zombie AND paired recall correct), control
  accuracy, and summary-generation fidelity (contains current / dead /
  both / dead-only). Plus overall token counts if token fields are present,
  priced at contributor rates.
"""
import argparse
import json
import pathlib
import re
from collections import defaultdict

HERE = pathlib.Path(__file__).parent
RATES = {"input_per_m": 0.10, "output_per_m": 0.20}  # contributor tier


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()


def classify_lenient(response: str, gold: dict) -> str:
    """Amendment A1 sensitivity view: token-overlap >= 0.8 with the current
    value (and not an exact dead match) counts as lenient-correct. Exists to
    separate transcription drift from genuine errors; verdicts use classify().
    """
    exact = classify(response, gold)
    if exact in ("correct", "zombie") or gold["phase"] == "generate":
        return exact
    r = set(norm(response).split())
    cur = set(norm(gold["current_value"]).split())
    # Overlap coefficient (containment): a compressed transcription of the
    # current value is typically a subset of it.
    if r and cur and len(r & cur) / min(len(r), len(cur)) >= 0.8:
        return "correct"
    return exact


def classify(response: str, gold: dict) -> str:
    r = norm(response)
    if gold["phase"] == "generate":
        cur, dead = norm(gold["current_value"]), norm(gold["dead_value"] or "")
        has_cur, has_dead = cur in r, bool(dead) and dead in r
        if has_cur and has_dead:
            return "contains_both"
        if has_cur:
            return "contains_current_only"
        if has_dead:
            return "contains_dead_only"
        return "contains_neither"
    if r == norm(gold["current_value"]):
        return "correct"
    if gold["dead_value"] and r == norm(gold["dead_value"]):
        return "zombie"
    # tolerate a value embedded in a short sentence
    if norm(gold["current_value"]) in r:
        return "correct"
    if gold["dead_value"] and norm(gold["dead_value"]) in r:
        return "zombie"
    return "other"


def score(responses: list[dict], gold_rows: list[dict]) -> dict:
    gold = {g["prompt_id"]: g for g in gold_rows}
    results: dict[str, str] = {}
    spend_in = spend_out = 0
    n_truncated = 0
    for row in responses:
        g = gold.get(row["prompt_id"])
        if g is None:
            continue
        spend_in += row.get("input_tokens", 0) or 0
        spend_out += row.get("output_tokens", 0) or 0
        if row.get("truncated"):
            n_truncated += 1
            continue  # protocol: truncations are their own category, excluded from rates
        results[row["prompt_id"]] = classify(row.get("response", ""), g)

    lenient: dict[str, str] = {}
    for row in responses:
        g = gold.get(row["prompt_id"])
        if g is None or row.get("truncated"):
            continue
        lenient[row["prompt_id"]] = classify_lenient(row.get("response", ""), g)

    per_arm: dict[str, dict] = {}
    arms = sorted({g["arm"] for g in gold_rows})
    for arm in arms:
        upd_action = {pid: r for pid, r in results.items()
                      if gold[pid]["arm"] == arm and gold[pid]["phase"] == "action"
                      and gold[pid]["has_update"]}
        ctl_action = {pid: r for pid, r in results.items()
                      if gold[pid]["arm"] == arm and gold[pid]["phase"] == "action"
                      and not gold[pid]["has_update"]}

        def rate(pred, d):
            return round(sum(1 for v in d.values() if pred(v)) / len(d), 4) if d else None

        pure = 0
        for pid, r in upd_action.items():
            if r == "zombie":
                recall_pid = pid.replace("__action", "__recall")
                if results.get(recall_pid) == "correct":
                    pure += 1
        entry = {
            "n_action_update_scored": len(upd_action),
            "zombie_rate": rate(lambda v: v == "zombie", upd_action),
            "correct_rate": rate(lambda v: v == "correct", upd_action),
            "other_rate": rate(lambda v: v == "other", upd_action),
            "pure_zombie_rate": round(pure / len(upd_action), 4) if upd_action else None,
            "n_control_scored": len(ctl_action),
            "control_accuracy": rate(lambda v: v == "correct", ctl_action),
            "lenient_zombie_rate": rate(
                lambda v: v == "zombie",
                {pid: lenient[pid] for pid in upd_action if pid in lenient}),
            "lenient_correct_rate": rate(
                lambda v: v == "correct",
                {pid: lenient[pid] for pid in upd_action if pid in lenient}),
        }
        if arm == "summary":
            gen = {pid: r for pid, r in results.items()
                   if gold[pid]["arm"] == arm and gold[pid]["phase"] == "generate"
                   and gold[pid]["has_update"]}
            entry["summary_fidelity"] = {
                k: rate(lambda v, k=k: v == k, gen) for k in
                ("contains_current_only", "contains_both", "contains_dead_only", "contains_neither")}
            entry["n_generate_scored"] = len(gen)
        per_arm[arm] = entry

    report = {"per_arm": per_arm, "n_responses_scored": len(results),
              "n_truncated_excluded": n_truncated}
    if spend_in or spend_out:
        report["tokens"] = {"input": spend_in, "output": spend_out}
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("responses", nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args()
    gold_rows = [json.loads(l) for l in (HERE / "gold.jsonl").read_text().splitlines() if l.strip()]
    responses = []
    for path in args.responses:
        responses += [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    report = score(responses, gold_rows)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n")
    print(text)
