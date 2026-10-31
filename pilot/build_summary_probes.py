#!/usr/bin/env python3
"""Render summary-arm probe prompts from model-written summaries.

Input:  summaries.jsonl with {"prompt_id": "<scenario>__summary__generate",
        "response": "<the memory note the model wrote>"}
Output: prompts_summary_probes.jsonl in the same record shape as
        prompts_prebuilt.jsonl (scorable against the same gold.jsonl).

The Stage A summary scenario's action probe is marked stage "A2"; all other
probes are stage "B". Usage:

    python3 build_summary_probes.py summaries.jsonl [out.jsonl]
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent


def render(summaries: list[dict], templates: list[dict]) -> list[dict]:
    by_scenario = {}
    for row in summaries:
        pid = row["prompt_id"]
        if not pid.endswith("__summary__generate"):
            continue  # responses.jsonl mixes phases; only generation rows count
        by_scenario[pid.split("__")[0]] = (row.get("response") or row.get("summary") or "").strip()
    stage_a_scenario = None
    manifest = json.loads((HERE / "manifest.json").read_text())
    for pid in manifest["stage_a_prompt_ids"]:
        if pid.endswith("__summary__generate"):
            stage_a_scenario = pid.split("__")[0]
    out = []
    for t in templates:
        summary = by_scenario.get(t["scenario_id"])
        if summary is None:
            continue
        prompt = t["template"].replace("{summary}", summary)
        stage = "A2" if (t["scenario_id"] == stage_a_scenario and t["phase"] == "action") else "B"
        out.append({
            "prompt_id": t["prompt_id"], "scenario_id": t["scenario_id"],
            "arm": "summary", "phase": t["phase"], "kind": t["kind"],
            "style": t["style"], "proximity": t["proximity"], "stage": stage,
            "prompt": prompt, "ws_tokens": len(prompt.split()),
            "summary_ws_tokens": len(summary.split()),
        })
    return out


if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "prompts_summary_probes.jsonl"
    summaries = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    templates = [json.loads(l) for l in (HERE / "summary_probe_templates.jsonl").read_text().splitlines() if l.strip()]
    rows = render(summaries, templates)
    dst.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    print(f"wrote {len(rows)} summary probe prompts to {dst}")
