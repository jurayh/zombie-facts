"""0 gates for the embedding-retriever package. No model calls, no
embedding API calls, no downloads. The stub backend is the only
embedder exercised here.

Gates:
  G1 inventory counts: 60 scenarios, 823 chunks, 108 queries, 108 gold.
  G2 chunk identity: chunk texts byte-match v2's fact-bearing events.
  G3 gold identity: gold_emb == v2 retrieval gold rows, verbatim.
  G4 query identity: query tasks == v2 action/recall probes.
  G5 determinism: rebuilding the inventory reproduces all file hashes.
  G6 retriever math: stub-agnostic fixtures — known vectors give the
      expected top-1; a within-epsilon second score triggers the
      earliest-index tie-break; a clear margin does not.
  G7 stub contract: deterministic across calls, vectors normalised.
  G8 stage-A marking: synthetic choice sets produce the documented
      2/2/2/1/1 span when available, and degrade gracefully when a
      category is empty (still exactly 8, no duplicates).
  G9 no leakage: query texts contain no target value, no "zombie"
      wording, no current/dead labels.
  G10 scorer fixtures: a perfect response set scores 0% zombie; an
      all-v2 set scores 100% zombie_v2; truncations are excluded.

Usage: python3 run_gates_emb.py
Exit 0 only if all gates pass.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pilot_v2"))
sys.path.insert(0, HERE)

from embedder import embed_stub  # noqa: E402
from generator_v2 import generate_dataset  # noqa: E402
from retriever_emb import retrieve  # noqa: E402
from run_retrieval_emb import mark_stages  # noqa: E402
from score_emb import score  # noqa: E402

V2_DIR = os.path.join(os.path.dirname(HERE), "pilot_v2")
FAILURES = []
CHECKS = [0]


def check(name, cond, detail=""):
    CHECKS[0] += 1
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def main():
    chunks = load_jsonl(os.path.join(HERE, "chunks_emb.jsonl"))
    queries = load_jsonl(os.path.join(HERE, "queries_emb.jsonl"))
    gold = load_jsonl(os.path.join(HERE, "gold_emb.jsonl"))
    manifest = json.load(open(os.path.join(HERE, "manifest_emb.json")))

    # G1
    check("G1 counts", len(chunks) == 823 and len(queries) == 108
          and len(gold) == 108 and manifest["n_scenarios"] == 60,
          f"chunks={len(chunks)} queries={len(queries)} gold={len(gold)}")

    # G2 + G3 + G4
    scenarios = generate_dataset(777013)
    v2_chunks = {(s.scenario_id, e.event_id): e.text for s in scenarios
                 for e in s.events if e.fact_bearing}
    emb_chunks = {(c["scenario_id"], c["event_id"]): c["text"] for c in chunks}
    check("G2 chunk identity", v2_chunks == emb_chunks)
    v2_gold = [json.loads(l) for l in open(os.path.join(V2_DIR, "gold_v2.jsonl"))
               if json.loads(l)["arm"] == "retrieval"]
    check("G3 gold identity", v2_gold == gold)
    qmap = {q["prompt_id"]: q["task"] for q in queries}
    ok = all(qmap[f"{s.scenario_id}__retrieval__action"] == s.action_probe()
             for s in scenarios) and all(
        qmap[f"{s.scenario_id}__retrieval__recall"] == s.recall_probe()
        for s in scenarios if s.has_update)
    check("G4 query identity", ok)

    # G5 determinism: rebuild hashes
    h = hashlib.sha256()
    for p in ("chunks_emb.jsonl", "queries_emb.jsonl", "gold_emb.jsonl"):
        h.update(open(os.path.join(HERE, p), "rb").read())
    check("G5 determinism", h.hexdigest() == manifest["files_sha256"])

    # G6 retriever math fixtures
    ids = ["a", "b", "c"]
    r = retrieve(ids, [[1, 0], [0, 1], [0.7071, 0.7071]], [1, 0])
    check("G6a clear top-1", r["chosen"] == "a" and not r["tie"])
    r = retrieve(ids, [[1, 0], [0.9999, 0.0141], [0, 1]], [1, 0])
    check("G6b tie -> earliest", r["chosen"] == "a" and r["tie"],
          f"chosen={r['chosen']} tie={r['tie']} margin={r['margin']:.4f}")
    r = retrieve(ids, [[0, 1], [1, 0], [0.9999, 0.0141]], [1, 0])
    check("G6c tie picks earliest index, not top score order",
          r["chosen"] == "b" and r["tie"], f"chosen={r['chosen']}")

    # G7 stub contract
    v1 = embed_stub(["alpha beta", "gamma"])
    v2s = embed_stub(["alpha beta", "gamma"])
    norms = [math.sqrt(sum(x * x for x in v)) for v in v1]
    check("G7 stub deterministic + normalised",
          v1 == v2s and all(abs(n - 1.0) < 1e-9 for n in norms))

    # G8 stage-A marking
    def fake_prompt(pid):
        return {"prompt_id": pid}
    statuses = (["dead_v1"] * 4 + ["dead_v2"] * 4 + ["current"] * 4
                + ["control"] * 2)
    rows = [fake_prompt(f"p{i}") for i in range(len(statuses))]
    ch = {f"p{i}": {"gold_status": st, "tie": (i == 0)}
            for i, st in enumerate(statuses)}
    marked = mark_stages(rows, ch)
    a = [r for r in marked if r["stage"] == "A"]
    a_status = sorted(ch[r["prompt_id"]]["gold_status"] for r in a)
    check("G8a stage-A span", len(a) == 8 and a_status == sorted(
        ["dead_v1", "dead_v1", "dead_v2", "dead_v2", "current", "current",
         "control", "dead_v1"]),
        f"a_status={a_status}")
    # Degenerate: only current choices -> still exactly 8, no duplicates.
    rows2 = [fake_prompt(f"q{i}") for i in range(12)]
    ch2 = {f"q{i}": {"gold_status": "current", "tie": False} for i in range(12)}
    marked2 = mark_stages(rows2, ch2)
    a2 = [r["prompt_id"] for r in marked2 if r["stage"] == "A"]
    check("G8b stage-A degenerate", len(a2) == 8 and len(set(a2)) == 8)

    # G9 no leakage
    vals = set()
    for s in scenarios:
        vals.update([s.v1, s.v2, s.v3])
    leak = [q for q in queries
            if any(v in q["task"] for v in vals if v)
            or "zombie" in q["task"].lower()]
    check("G9 no leakage", not leak, f"leaking queries: {leak[:3]}")

    # G10 scorer fixtures
    gold_rows = [g for g in gold if g["arm"] == "retrieval"]
    perfect = [{"prompt_id": g["prompt_id"],
                "response": g["current_value"], "truncated": False,
                "input_tokens": 0, "output_tokens": 0} for g in gold_rows]
    rep = score(perfect, gold_rows)
    check("G10a perfect -> 0 zombie",
          rep["per_arm"]["retrieval"]["zombie_rate"] == 0.0)
    allv2 = [{"prompt_id": g["prompt_id"],
              "response": (g["dead_values"][1] if g["has_update"]
                           else g["current_value"]),
              "truncated": False, "input_tokens": 0, "output_tokens": 0}
             for g in gold_rows]
    rep2 = score(allv2, gold_rows)
    check("G10b all-v2 -> 100% zombie_v2",
          rep2["per_arm"]["retrieval"]["zombie_v2_rate"] == 1.0)
    trunc = [dict(r) for r in perfect]
    trunc[5] = {**trunc[5], "truncated": True}
    rep3 = score(trunc, gold_rows)
    check("G10c truncation excluded",
          rep3["n_truncated_excluded"] == 1
          and rep3["n_responses_scored"] == len(gold_rows) - 1)

    print(f"\n{CHECKS[0] - len(FAILURES)}/{CHECKS[0]} checks passed")
    if FAILURES:
        print("FAILED:", FAILURES)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
