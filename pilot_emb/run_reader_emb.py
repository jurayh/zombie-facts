#!/usr/bin/env python3
"""Run the approved Zombie Facts embedding-retriever reader stage on the Meta Model API.

Reader prompts come from run_retrieval_emb.py (stage R); this script
only makes reader calls. It is NOT run as part of the 0 package
build; it runs only under an approved proposal.

Reader-stage approval: approved sub-caps (see proposal),
all stages, model
muse-spark-1.3-contributor. This runner enforces the cap itself: it tracks
actual billed tokens from each response's usage block and refuses to start
a wave whose conservative estimate would cross the cap.

Usage:
    python3 run_reader_emb.py --stage A     # 8 prebuilt calibration prompts
    python3 run_reader_emb.py --stage A2 --prompts prompts_summary_probes_stageA.jsonl
    python3 run_reader_emb.py --stage B     # remaining prebuilt prompts
    python3 run_reader_emb.py --stage B  --prompts prompts_summary_probes.jsonl  (stage B rows)

Resumable: prompt_ids with a completed, non-empty response record in
responses.jsonl are skipped. Every attempt (including truncations) is
ledgered in responses.jsonl and counted against the cap.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request, read_json_response

API = "https://api.meta.ai/v1/responses"
ALLOWED = ("api.meta.ai",)
MODEL = "muse-spark-1.3-contributor"
IN_RATE = 0.10 / 1_000_000
OUT_RATE = 0.20 / 1_000_000
CAP = 0.05
BPE_UPPER = 1.4
OUT_CAPS = {"action": 1024, "recall": 1024}

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw_emb"
RESPONSES = ROOT / "responses_emb.jsonl"


def post(body: dict) -> tuple[int, dict, float]:
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    add_surrogate_to_request(req, "custom.meta-model-api",
                             entry_name="access_token", allowed_hosts=ALLOWED)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, read_json_response(resp), round(time.time() - started, 2)
    except urllib.error.HTTPError as e:
        return e.code, {"error_body": e.read().decode(errors="replace")[:1500]}, \
            round(time.time() - started, 2)
    except Exception as e:  # noqa: BLE001
        return -1, {"error": f"{type(e).__name__}: {e}"}, round(time.time() - started, 2)


def output_text_of(payload: dict) -> str:
    text = ""
    for item in (payload or {}).get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") == "output_text" and part.get("text"):
                text += part["text"]
    return text.strip()


def load_done() -> tuple[set[str], float]:
    done, spent = set(), 0.0
    if RESPONSES.exists():
        for line in RESPONSES.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            spent += r.get("cost_usd") or 0.0
            if r.get("http") == 200 and r.get("status_field") == "completed" \
                    and (r.get("response") or "").strip():
                done.add(r["prompt_id"])
    return done, spent


def est_cost(row: dict) -> float:
    import math
    return math.ceil(row["ws_tokens"] * BPE_UPPER) * IN_RATE \
        + OUT_CAPS[row["phase"]] * OUT_RATE


def run_one(row: dict) -> dict:
    body = {
        "model": MODEL,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": row["prompt"]}]}],
        "stream": False,
        "temperature": 0,
        "max_output_tokens": OUT_CAPS[row["phase"]],
        "reasoning": {"effort": "low"},
    }
    status, payload, latency = post(body)
    usage = payload.get("usage") or {}
    tin = usage.get("input_tokens") or 0
    tout = usage.get("output_tokens") or 0
    reasoning = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
    incomplete = (payload.get("incomplete_details") or {}).get("reason")
    truncated = payload.get("status") == "incomplete" or incomplete == "max_output_tokens"
    cost = tin * IN_RATE + tout * OUT_RATE
    RAW.mkdir(exist_ok=True)
    slug = row["prompt_id"].replace(":", "__").replace("/", "_")
    (RAW / f"{slug}.json").write_text(json.dumps(payload)[:2_000_000])
    return {"prompt_id": row["prompt_id"], "scenario_id": row["scenario_id"],
            "arm": row["arm"], "phase": row["phase"], "run_stage": row["stage"],
            "http": status, "status_field": payload.get("status"),
            "truncated": bool(truncated), "latency_s": latency,
            "input_tokens": tin, "output_tokens": tout,
            "reasoning_tokens": reasoning, "cost_usd": round(cost, 6),
            "response": output_text_of(payload),
            "error_body": payload.get("error_body") or payload.get("error")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--prompts", default="prompts_emb.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    rows = [json.loads(l) for l in (ROOT / args.prompts).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r["stage"] == args.stage]
    done, spent = load_done()
    todo = [r for r in rows if r["prompt_id"] not in done]
    print(f"stage {args.stage} ({args.prompts}): {len(todo)} calls to make, "
          f"{spent:.5f} already spent, cap {CAP:.2f}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i in range(0, len(todo), args.workers):
            wave = todo[i:i + args.workers]
            wave_est = sum(est_cost(r) for r in wave)
            if spent + wave_est > CAP:
                print(f"STOP: budget guard — spent {spent:.5f} + wave est "
                      f"{wave_est:.5f} would cross cap {CAP:.2f}", flush=True)
                return 2
            recs = list(ex.map(run_one, wave))
            with open(RESPONSES, "a") as f:
                for rec in recs:
                    f.write(json.dumps(rec) + "\n")
                    spent += rec["cost_usd"]
                    print(f"{rec['prompt_id']} http={rec['http']} "
                          f"in={rec['input_tokens']} out={rec['output_tokens']} "
                          f"reasoning={rec['reasoning_tokens']} trunc={rec['truncated']} "
                          f"{rec['cost_usd']:.5f} total={spent:.5f}", flush=True)
                    if rec["http"] != 200:
                        print(f"  ERROR: {str(rec['error_body'])[:300]}", flush=True)
    print(f"stage {args.stage} done. cumulative spent {spent:.5f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
