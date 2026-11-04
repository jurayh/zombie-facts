"""Tie-epsilon counterfactual for the embedding retriever.

The shipped sensitivity section is a margin-bucket re-cut: it says how
many dead choices are confident at each threshold, but it cannot say
what the retriever would have chosen at another epsilon, because the
original run saved only the chosen chunk. This script answers that
question from retrieval_rankings_emb.jsonl, with no re-embedding.

Method: for each probe and each epsilon E, the counterfactual choice
is the earliest-index chunk whose score is within E of the top score
— exactly the retriever's tie rule, re-applied. E = 0.02 reproduces
the as-run choices, which the script verifies against
retrieval_choices_emb.jsonl for all 108 probes before reporting
anything; a mismatch exits non-zero.

What it reports, per epsilon, over the 48 action updates:
  dead rate (the retrieval-level headline under that epsilon),
  dead_v1 / dead_v2 split, choices changed vs 0.02 and their
  direction, and the clear-win-only dead rate (dead choices whose
  margin is at least E — the re-cut figure, recomputed here from the
  rankings so the two views can be compared).
Control accuracy (chosen value == current value, 12 controls) is
reported alongside.

Output: a table on stdout and results/counterfactual_epsilon.json.

Limits: retrieval-level only. The reader headline (78.7%) was measured
on the 0.02 choices and is not recomputed here — a reader re-run on
counterfactual choices would be a new run, not this script. The
reader was faithful to the retrieved chunk in 106/107 responses, so
the retrieval dead rate tracks the reader zombie rate closely, but
the two are not the same number and this script does not equate them.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EPSILONS = [0.05, 0.02, 0.01, 0.005, 0.002, 0.0]


def choose_at_epsilon(ranking, epsilon):
    """Earliest-index chunk within epsilon of the top score.

    ranking: [[original index, chunk id, score], ...] sorted by score
    desc. Returns the chosen chunk id.
    """
    top = ranking[0][2]
    tied = [r for r in ranking if r[2] >= top - epsilon]
    return min(tied, key=lambda r: r[0])[1]


def classify(value, gold):
    if not gold["has_update"]:
        return "control"
    if value == gold["current_value"]:
        return "current"
    if value == gold["dead_values"][0]:
        return "dead_v1"
    if value == gold["dead_values"][1]:
        return "dead_v2"
    return "other"


def load(name):
    with open(os.path.join(HERE, name)) as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    rankings = load("retrieval_rankings_emb.jsonl")
    chunks = {c["event_id"]: c for c in load("chunks_emb.jsonl")}
    gold = {g["prompt_id"]: g for g in load("gold_emb.jsonl")}
    choices = {c["prompt_id"]: c
               for c in load("retrieval_choices_emb.jsonl")}

    # Verification: E = 0.02 must reproduce the as-run choices exactly.
    mismatches = []
    for row in rankings:
        got = choose_at_epsilon(row["ranking"], 0.02)
        want = choices[row["prompt_id"]]["chosen_event_id"]
        if got != want:
            mismatches.append((row["prompt_id"], got, want))
    if mismatches:
        print(f"VERIFICATION FAILED: {len(mismatches)} choices at 0.02 "
              "do not match retrieval_choices_emb.jsonl")
        for m in mismatches[:5]:
            print(" ", m)
        sys.exit(1)
    print(f"verified: 0.02 reproduces all {len(rankings)} as-run choices")

    actions = [r for r in rankings if r["phase"] == "action"
               and gold[r["prompt_id"]]["has_update"]]
    controls = [r for r in rankings
                if not gold[r["prompt_id"]]["has_update"]]
    base = {r["prompt_id"]: choose_at_epsilon(r["ranking"], 0.02)
            for r in rankings}

    out = {}
    print(f"\naction updates: {len(actions)}; controls: {len(controls)}")
    print(f"{'eps':>6} {'dead':>5} {'rate':>6} {'v1':>3} {'v2':>3} "
          f"{'changed':>8} {'to_dead':>8} {'to_curr':>8} "
          f"{'clear_dead':>10} {'ctrl_ok':>8}")
    for eps in EPSILONS:
        dead = v1 = v2 = changed = to_dead = to_curr = clear_dead = 0
        for row in actions:
            g = gold[row["prompt_id"]]
            chosen = choose_at_epsilon(row["ranking"], eps)
            status = classify(chunks[chosen]["value"], g)
            if status in ("dead_v1", "dead_v2"):
                dead += 1
                if status == "dead_v1":
                    v1 += 1
                else:
                    v2 += 1
            if chosen != base[row["prompt_id"]]:
                changed += 1
                new_status = status
                old_status = classify(
                    chunks[base[row["prompt_id"]]]["value"], g)
                if new_status in ("dead_v1", "dead_v2") and \
                        old_status not in ("dead_v1", "dead_v2"):
                    to_dead += 1
                if new_status == "current" and \
                        old_status in ("dead_v1", "dead_v2"):
                    to_curr += 1
            margin = row["ranking"][0][2] - row["ranking"][1][2]
            if margin >= eps and status in ("dead_v1", "dead_v2"):
                clear_dead += 1
        ctrl_ok = sum(
            1 for row in controls
            if chunks[choose_at_epsilon(row["ranking"], eps)]["value"]
            == gold[row["prompt_id"]]["current_value"])
        out[str(eps)] = {
            "dead": dead, "dead_rate": dead / len(actions),
            "dead_v1": v1, "dead_v2": v2, "changed_vs_0.02": changed,
            "changed_to_dead": to_dead, "changed_to_current": to_curr,
            "clear_win_only_dead": clear_dead,
            "control_current": ctrl_ok,
        }
        print(f"{eps:>6} {dead:>5} {dead / len(actions):>6.1%} {v1:>3} "
              f"{v2:>3} {changed:>8} {to_dead:>8} {to_curr:>8} "
              f"{clear_dead:>10} {ctrl_ok:>8}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results",
                            "counterfactual_epsilon.json"), "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    print("\nwrote results/counterfactual_epsilon.json")


if __name__ == "__main__":
    main()
