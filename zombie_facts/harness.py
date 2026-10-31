"""Harness: run scenarios through arms x the reference agent, score, judge.

Scoring per update scenario (action probe):
  correct  answer == current (v2) value
  zombie   answer == dead (v1) value while a live replacement exists
  other    anything else / no answer

Paired v2-recall probe: the SAME scenario re-run with the proximity
re-mention removed and a direct "what is the current value?" question.
Its job is attribution:
  pure zombie      action probe is zombie AND paired recall returns v2
                   (the agent could produce the live fact when asked
                   cleanly, but acted on the dead one in context)
  explained zombie action probe is zombie AND paired recall also fails
                   (consistent with never having the live fact usable)

Kill criteria (pre-registered in the spike brief):
  K1  zombie rates near zero across arms (max arm rate < 0.05)
      -> nothing to measure, STOP
  K2  zombie rates high everywhere (min arm rate > 0.20) AND almost fully
      explained by v2 recall failure (pure-zombie share of all zombies
      < 0.10) -> ordinary forgetting; fold into the Compaction Kit, STOP
  otherwise -> GO: the effect exists, separates arms, and is not just
  recall failure. (GO here licenses a *costed proposal* for a live arm,
  not a live run.)
"""
from __future__ import annotations

from collections import defaultdict

from .agents import NearestMentionAgent, OracleAgent, PrimacyAgent
from .arms import ARMS
from .generator import Scenario, generate_dataset


def _run_trial(seed: int, scenario: Scenario, arm, agent, strip_remention: bool) -> str | None:
    events = [e for e in scenario.events
              if not (strip_remention and e.kind in ("remention_dead", "remention_live"))]
    pres = arm.present(seed, scenario, events)
    return agent.answer(seed, scenario, pres, ground_truth=scenario.current_value)


def _rate(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def run(seed: int = 42, replicates: int = 5) -> dict:
    scenarios = generate_dataset(seed, replicates)
    updates = [s for s in scenarios if s.has_update]
    controls = [s for s in scenarios if not s.has_update]
    agent = NearestMentionAgent()

    per_arm: dict[str, dict] = {}
    for arm_name, arm_cls in ARMS.items():
        arm = arm_cls()
        rows = []
        for s in updates:
            action = _run_trial(seed, s, arm, agent, strip_remention=False)
            recall = _run_trial(seed, s, arm, agent, strip_remention=True)
            rows.append({
                "scenario": s.scenario_id, "kind": s.kind, "style": s.update_style,
                "proximity": s.proximity,
                "zombie": action == s.dead_value and s.dead_value != s.current_value,
                "correct": action == s.current_value,
                "recall_ok": recall == s.current_value,
            })
        n = len(rows)
        zombies = [r for r in rows if r["zombie"]]
        pure = [r for r in zombies if r["recall_ok"]]

        def breakdown(key: str) -> dict:
            out: dict[str, dict] = {}
            groups: dict[str, list] = defaultdict(list)
            for r in rows:
                groups[r[key]].append(r)
            for g, rs in sorted(groups.items()):
                out[g] = {"n": len(rs), "zombie_rate": _rate(sum(x["zombie"] for x in rs), len(rs))}
            return out

        ctl_correct = sum(
            _run_trial(seed, s, arm, agent, strip_remention=False) == s.current_value
            for s in controls)

        per_arm[arm_name] = {
            "n_update": n,
            "zombie_rate": _rate(len(zombies), n),
            "correct_rate": _rate(sum(r["correct"] for r in rows), n),
            "other_rate": _rate(n - len(zombies) - sum(r["correct"] for r in rows), n),
            "v2_recall_failure_rate": _rate(sum(not r["recall_ok"] for r in rows), n),
            "pure_zombie_rate": _rate(len(pure), n),
            "zombie_explained_share": _rate(len(zombies) - len(pure), len(zombies)) if zombies else 0.0,
            "no_update_control_accuracy": _rate(ctl_correct, len(controls)),
            "by_style": breakdown("style"),
            "by_proximity": breakdown("proximity"),
            "by_kind": breakdown("kind"),
        }

    # Sanity gates on the raw arm
    raw = ARMS["raw_transcript"]()
    oracle_zombies = sum(
        _run_trial(seed, s, raw, OracleAgent(), strip_remention=False) == s.dead_value
        and s.dead_value != s.current_value for s in updates)
    primacy_answers = [_run_trial(seed, s, raw, PrimacyAgent(), strip_remention=False) for s in updates]
    primacy_zombie_rate = _rate(
        sum(a == s.dead_value and s.dead_value != s.current_value
            for a, s in zip(primacy_answers, updates)), len(updates))

    rates = [a["zombie_rate"] for a in per_arm.values()]
    total_zombies = sum(a["zombie_rate"] * a["n_update"] for a in per_arm.values())
    total_pure = sum(a["pure_zombie_rate"] * a["n_update"] for a in per_arm.values())
    pure_share = (total_pure / total_zombies) if total_zombies else 0.0

    if max(rates) < 0.05:
        verdict, verdict_code = (
            "KILL (K1): zombie rates near zero across arms — nothing to measure.", "kill_k1")
    elif min(rates) > 0.20 and pure_share < 0.10:
        verdict, verdict_code = (
            "KILL (K2): zombie rates high everywhere and almost fully explained by "
            "v2 recall failure — ordinary forgetting; fold into the Compaction Kit.", "kill_k2")
    else:
        verdict, verdict_code = (
            "GO: zombie effect is measurable, separates memory architectures, and is "
            "not fully explained by v2 recall failure. Licenses a costed live-arm "
            "proposal only; no live run is authorised by this verdict.", "go")

    # Measured context size for any future live-arm cost proposal: the raw
    # transcript is the largest presentation; tokens approximated chars/4.
    raw_chars = [sum(len(e.text) for e in s.events) for s in updates]
    mean_raw_chars = sum(raw_chars) / len(raw_chars) if raw_chars else 0

    return {
        "seed": seed,
        "n_update_scenarios": len(updates),
        "n_control_scenarios": len(controls),
        "reference_agent": agent.name,
        "arms": per_arm,
        "arm_separation_max_minus_min": round(max(rates) - min(rates), 4),
        "pure_zombie_share_of_all_zombies": round(pure_share, 4),
        "sanity": {
            "oracle_zombie_count_raw": oracle_zombies,
            "primacy_zombie_rate_raw": primacy_zombie_rate,
        },
        "mean_raw_context_chars": round(mean_raw_chars, 1),
        "mean_raw_context_tokens_approx": round(mean_raw_chars / 4, 1),
        "verdict_code": verdict_code,
        "verdict": verdict,
    }


def render_markdown(res: dict) -> str:
    lines = [
        "# Zombie Facts — spike results (scripted/reference arms, offline)",
        "",
        f"Seed {res['seed']} · {res['n_update_scenarios']} update scenarios · "
        f"{res['n_control_scenarios']} no-update controls · reference agent: "
        f"`{res['reference_agent']}` (nearest encoded mention wins).",
        "",
        "## Headline: Zombie Rate by memory arm",
        "",
        "| Memory arm | Zombie rate | Correct | Other | v2 recall failure | Pure zombie rate | No-update control acc. |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, a in res["arms"].items():
        lines.append(
            f"| {name} | **{a['zombie_rate']:.1%}** | {a['correct_rate']:.1%} | "
            f"{a['other_rate']:.1%} | {a['v2_recall_failure_rate']:.1%} | "
            f"{a['pure_zombie_rate']:.1%} | {a['no_update_control_accuracy']:.1%} |")
    lines += [
        "",
        f"Arm separation (max − min zombie rate): **{res['arm_separation_max_minus_min']:.1%}**. "
        f"Pure zombies (recall OK, action zombie) are "
        f"**{res['pure_zombie_share_of_all_zombies']:.1%}** of all zombie answers.",
        "",
        "## Zombie rate by proximity (raw transcript arm)",
        "",
        "| Proximity | Zombie rate | n |",
        "|---|---:|---:|",
    ]
    for prox, b in res["arms"]["raw_transcript"]["by_proximity"].items():
        lines.append(f"| {prox} | {b['zombie_rate']:.1%} | {b['n']} |")
    lines += ["", "## Zombie rate by update style", "",
              "| Style | " + " | ".join(res["arms"].keys()) + " |",
              "|---|" + "---:|" * len(res["arms"])]
    for style in ("direct", "paraphrase", "document", "tool_result"):
        row = " | ".join(f"{res['arms'][a]['by_style'][style]['zombie_rate']:.1%}" for a in res["arms"])
        lines.append(f"| {style} | {row} |")
    lines += [
        "",
        "## Sanity gates",
        "",
        f"- Oracle agent zombies on raw arm: {res['sanity']['oracle_zombie_count_raw']} (required 0)",
        f"- Primacy agent zombie rate on raw arm: {res['sanity']['primacy_zombie_rate_raw']:.1%} (required 100%)",
        "",
        "## Verdict vs pre-registered kill criteria",
        "",
        res["verdict"],
        "",
        "_Scope limit: these are scripted/reference arms under a stated reader model. "
        "They validate the generator, harness, controls and scorer end to end and show "
        "the metric CAN separate architectures. They are not evidence about any real "
        "LLM or production memory system; that requires the live arm, which needs a "
        "separate costed proposal and explicit approval._",
        "",
    ]
    return "\n".join(lines)
