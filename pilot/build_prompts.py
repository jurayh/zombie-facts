#!/usr/bin/env python3
"""Build the Zombie Facts live-pilot prompt corpus offline (no model calls).

Pilot design (see PROTOCOL.md):
  * Fresh scenarios, seed 90210 — disjoint from the offline spike corpus (seed 42).
  * 96 update scenarios: 4 update styles x 3 proximities x 8 replicates,
    fact kinds rotated so every style x proximity cell holds each kind twice.
  * 24 no-update controls: 4 kinds x 6.
  * Raw-arm and summary-generation prompts carry a transcript padded with
    neutral filler to ~2,000 whitespace tokens (real session lengths, not
    the spike's ~108-token toy contexts).
  * Retrieval and versioned prompts present the reference arm's artifact
    (top-ranked chunk / current record) — short by construction.
  * Summary-arm probe prompts cannot be prebuilt (they embed a model-written
    summary); summary_probe_templates.jsonl carries a {summary} template per
    scenario/probe, rendered later by build_summary_probes.py.

Outputs (this directory):
  prompts_prebuilt.jsonl        model-facing prompts, no gold values labelled
  gold.jsonl                    scoring gold for every prompt incl. summary probes
  summary_probe_templates.jsonl {summary} templates for the summary arm
  manifest.json                 counts, token measurements, hashes
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from zombie_facts.arms import RetrievalArm, VersionedArm
from zombie_facts.generator import KINDS, PROXIMITIES, STYLES, Scenario, make_scenario

PILOT_SEED = 90210
SPIKE_SEED = 42
TARGET_TOKENS = 2000  # whitespace tokens per padded transcript
TOKEN_LO, TOKEN_HI = 1900, 2120

ANSWER_INSTRUCTION = (
    "You are an agent with access to memory from earlier sessions. Use only the "
    "memory below. Reply with the exact value only, and nothing else."
)
SUMMARY_INSTRUCTION = (
    "Read the session history below and write a compact memory note for future "
    "use. Preserve every concrete fact in the history, including any changes to "
    "facts, with the entity each fact belongs to. Write at most 180 words. "
    "Do not answer any question; write only the memory note."
)

# Neutral filler sentences: no digits, no pilot entity names, no fact words
# that could collide with a target value.
_FILLER_SENTENCES = [
    "The morning conversation drifted to office plants and which ones survive low light.",
    "Someone described a long train ride through farmland and small towns.",
    "There was a debate about whether soup counts as a meal on its own.",
    "A story about a neighbour who collects postcards from strangers came up again.",
    "The group traded tips for keeping herbs alive on a windowsill.",
    "Talk turned to favourite walking routes and the quiet streets after rain.",
    "Someone recalled a school play with cardboard trees and a painted moon.",
    "There was gentle disagreement about the best way to brew loose leaf tea.",
    "A anecdote about a lost umbrella on a windy pier made the rounds.",
    "The chat lingered on book recommendations nobody had finished yet.",
    "Someone described learning to whistle with two fingers as a child.",
    "There was talk of a farmers market stall that sells only honey.",
    "A memory of summer storms and power cuts in a small apartment surfaced.",
    "The group compared notes on keeping sourdough starter alive in winter.",
    "Someone told a story about a cat that rides the porch rail like a train.",
    "Conversation wandered to old board games and house rules nobody agrees on.",
    "There was a long tangent about the smell of rain on hot pavement.",
    "Someone described a workshop where they repair broken ceramics with gold.",
    "Talk turned to constellations and misremembered star names.",
    "A story about a grandfather who labelled every jar in the pantry was shared.",
    "The group discussed whether houseplants prefer music or silence.",
    "Someone recalled a ferry ride with gulls following the wake for miles.",
    "There was a debate about jam flavours and which ones belong on toast.",
    "A anecdote about learning to juggle with oranges came up.",
    "The conversation drifted to winter scarves and lost gloves.",
    "Someone described a tiny museum devoted to door knockers.",
    "Talk turned to picnic blankets and the etiquette of sharing shade.",
    "There was a story about a dog that waits for the mail every morning.",
    "The group traded memories of school lunches and traded snacks.",
    "Someone mentioned a choir that rehearses in a parking garage for the echo.",
]


def ws_tokens(text: str) -> int:
    return len(text.split())


def _filler_sentences(seed_key: str, want_tokens: int) -> str:
    """Deterministic filler text of roughly want_tokens whitespace tokens."""
    out: list[str] = []
    total = 0
    i = 0
    while total < want_tokens:
        h = hashlib.sha256(f"{seed_key}|{i}".encode()).hexdigest()
        sent = _FILLER_SENTENCES[int(h[:8], 16) % len(_FILLER_SENTENCES)]
        t = ws_tokens(sent)
        if total + t > want_tokens + 12 and out:
            break
        out.append(sent)
        total += t
        i += 1
    return " ".join(out)


def padded_transcript(scenario: Scenario, strip_remention: bool) -> str:
    """Render the scenario history as a session transcript padded to target."""
    events = [e for e in scenario.events
              if not (strip_remention and e.kind in ("remention_dead", "remention_live"))]
    base = sum(ws_tokens(e.text) for e in events)
    filler_sessions = [e for e in events if e.kind == "filler"]
    need = max(0, TARGET_TOKENS - base)
    per_session = need // max(1, len(filler_sessions))
    blocks: list[str] = []
    for e in events:
        if e.kind == "filler":
            text = _filler_sentences(
                f"{PILOT_SEED}|{scenario.scenario_id}|s{e.session}|strip{strip_remention}",
                per_session)
            blocks.append(f"Session {e.session} notes: {text}")
        else:
            blocks.append(f"Session {e.session}: {e.text}")
    return "\n".join(blocks)


def pilot_dataset() -> list[Scenario]:
    scenarios: list[Scenario] = []
    n = 0
    for si, style in enumerate(STYLES):
        for pi, prox in enumerate(PROXIMITIES):
            for r in range(8):
                kind = KINDS[(r + si + pi) % len(KINDS)]
                sid = f"pilot-upd-{n:03d}"
                scenarios.append(make_scenario(PILOT_SEED, sid, kind, style, prox, r))
                n += 1
    for ki, kind in enumerate(KINDS):
        for r in range(6):
            sid = f"pilot-ctl-{ki * 6 + r:03d}"
            scenarios.append(make_scenario(PILOT_SEED, sid, kind, None, "none", r))
    return scenarios


def _answer_prompt(memory_label: str, memory_text: str, task: str) -> str:
    return f"{ANSWER_INSTRUCTION}\n\n{memory_label}\n{memory_text}\n\nTask: {task}"


# Stage A (smoke) selection: filled in build() once scenario indices exist.
STAGE_A_KEYS: set[tuple[str, str, str]] = set()  # (scenario_id, arm, phase)


def build() -> dict:
    scenarios = pilot_dataset()
    retrieval = RetrievalArm()
    versioned = VersionedArm()

    prompts: list[dict] = []
    gold: list[dict] = []
    templates: list[dict] = []

    def add_prompt(s: Scenario, arm: str, phase: str, prompt: str, stage: str = "B"):
        pid = f"{s.scenario_id}__{arm}__{phase}"
        prompts.append({
            "prompt_id": pid, "scenario_id": s.scenario_id, "arm": arm, "phase": phase,
            "kind": s.kind, "style": s.update_style, "proximity": s.proximity,
            "stage": stage, "prompt": prompt, "ws_tokens": ws_tokens(prompt),
        })
        return pid

    def add_gold(s: Scenario, arm: str, phase: str):
        gold.append({
            "prompt_id": f"{s.scenario_id}__{arm}__{phase}",
            "scenario_id": s.scenario_id, "arm": arm, "phase": phase,
            "kind": s.kind, "style": s.update_style, "proximity": s.proximity,
            "has_update": s.has_update,
            "current_value": s.current_value,
            "dead_value": s.dead_value if s.has_update else None,
        })

    # Pick Stage A scenarios deterministically: first dead_near/tool_result
    # update, first live_near/direct update, first control.
    upd = [s for s in scenarios if s.has_update]
    ctl = [s for s in scenarios if not s.has_update]
    a_dead = next(s for s in upd if s.proximity == "dead_near" and s.update_style == "tool_result")
    a_live = next(s for s in upd if s.proximity == "live_near" and s.update_style == "direct")
    a_para = next(s for s in upd if s.update_style == "paraphrase")
    stage_a: set[tuple[str, str, str]] = {
        (a_dead.scenario_id, "raw_transcript", "action"),
        (a_dead.scenario_id, "raw_transcript", "recall"),
        (a_live.scenario_id, "raw_transcript", "action"),
        (a_para.scenario_id, "retrieval", "action"),
        (a_dead.scenario_id, "versioned", "action"),
        (a_dead.scenario_id, "summary", "generate"),
        (a_para.scenario_id, "retrieval", "recall"),
        (ctl[0].scenario_id, "raw_transcript", "action"),
    }

    for s in scenarios:
        phases = ("action", "recall") if s.has_update else ("action",)
        # raw transcript (action on full history, recall on re-mention-stripped)
        for phase in phases:
            strip = phase == "recall"
            prompt = _answer_prompt("Memory (session history):",
                                    padded_transcript(s, strip),
                                    s.action_probe() if phase == "action" else s.recall_probe())
            stage = "A" if (s.scenario_id, "raw_transcript", phase) in stage_a else "B"
            add_prompt(s, "raw_transcript", phase, prompt, stage)
            add_gold(s, "raw_transcript", phase)
        # retrieval + versioned artifacts
        for arm_name, arm in (("retrieval", retrieval), ("versioned", versioned)):
            pres = arm.present(PILOT_SEED, s, s.events)
            cand = pres.candidates[0] if pres.candidates else None
            if arm_name == "retrieval":
                label = "Memory (retrieved record):"
                text = next((e.text for e in s.events if cand and e.event_id == cand.event_id), "")
            else:
                label = "Memory (current record):"
                text = f"{s.entity} — the {s.attribute} is {cand.value}." if cand else ""
            for phase in phases:
                prompt = _answer_prompt(label, text,
                                        s.action_probe() if phase == "action" else s.recall_probe())
                stage = "A" if (s.scenario_id, arm_name, phase) in stage_a else "B"
                add_prompt(s, arm_name, phase, prompt, stage)
                add_gold(s, arm_name, phase)
        # summary generation (model writes the memory note live)
        gen_prompt = (f"{SUMMARY_INSTRUCTION}\n\nSession history:\n"
                      f"{padded_transcript(s, strip_remention=False)}")
        stage = "A" if (s.scenario_id, "summary", "generate") in stage_a else "B"
        add_prompt(s, "summary", "generate", gen_prompt, stage)
        add_gold(s, "summary", "generate")
        # summary probe templates (rendered after summaries exist)
        for phase in phases:
            task = s.action_probe() if phase == "action" else s.recall_probe()
            templates.append({
                "prompt_id": f"{s.scenario_id}__summary__{phase}",
                "scenario_id": s.scenario_id, "arm": "summary", "phase": phase,
                "kind": s.kind, "style": s.update_style, "proximity": s.proximity,
                "template": _answer_prompt("Memory (your memory note):", "{summary}", task),
                "overhead_ws_tokens": ws_tokens(
                    _answer_prompt("Memory (your memory note):", "", task)),
            })
            add_gold(s, "summary", phase)

    # ---- manifest / measurements -------------------------------------------
    by_arm_phase = Counter((p["arm"], p["phase"]) for p in prompts)
    raw_ws = [p["ws_tokens"] for p in prompts
              if p["arm"] == "raw_transcript" or (p["arm"] == "summary" and p["phase"] == "generate")]
    total_ws = sum(p["ws_tokens"] for p in prompts)
    n_summary_probes = len(templates)
    # Summary-probe input estimate: template overhead + up to 250 words of
    # summary allowance (instruction caps summaries at 180 words; 250 is the
    # conservative planning allowance), per template.
    summary_probe_ws_est = sum(t["overhead_ws_tokens"] + 250 for t in templates)
    manifest = {
        "pilot_seed": PILOT_SEED,
        "spike_seed": SPIKE_SEED,
        "n_scenarios": len(scenarios),
        "n_update_scenarios": len(upd),
        "n_control_scenarios": len(ctl),
        "n_prebuilt_prompts": len(prompts),
        "n_summary_probe_templates": n_summary_probes,
        "n_total_planned_calls": len(prompts) + n_summary_probes,
        "n_summary_generate_calls": sum(1 for p in prompts if p["phase"] == "generate"),
        "prebuilt_by_arm_phase": {f"{a}/{ph}": c for (a, ph), c in sorted(by_arm_phase.items())},
        "prebuilt_ws_tokens_total": total_ws,
        "padded_prompt_ws_tokens_min": min(raw_ws),
        "padded_prompt_ws_tokens_max": max(raw_ws),
        "padded_prompt_ws_tokens_mean": round(sum(raw_ws) / len(raw_ws), 1),
        "summary_probe_ws_tokens_est": summary_probe_ws_est,
        "total_input_ws_tokens_est": total_ws + summary_probe_ws_est,
        "bpe_upper_factor": 1.4,
        "stage_a_prompt_ids": sorted(p["prompt_id"] for p in prompts if p["stage"] == "A"),
        "model": "muse-spark-1.3-contributor",
        "output_caps": {"action": 1024, "recall": 1024, "generate": 1536},
        "expected_output_tokens_per_call": {"action": 650, "recall": 650, "generate": 900},
    }
    return {"prompts": prompts, "gold": gold, "templates": templates, "manifest": manifest}


def _dump(name: str, rows: list[dict], outdir: pathlib.Path):
    text = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    (outdir / name).write_text(text)
    return hashlib.md5(text.encode()).hexdigest()


if __name__ == "__main__":
    outdir = pathlib.Path(__file__).parent
    built = build()
    hashes = {
        "prompts_prebuilt.jsonl": _dump("prompts_prebuilt.jsonl", built["prompts"], outdir),
        "gold.jsonl": _dump("gold.jsonl", built["gold"], outdir),
        "summary_probe_templates.jsonl": _dump(
            "summary_probe_templates.jsonl", built["templates"], outdir),
    }
    built["manifest"]["file_md5"] = hashes
    (outdir / "manifest.json").write_text(
        json.dumps(built["manifest"], indent=2, sort_keys=True) + "\n")
    print(json.dumps(built["manifest"], indent=2, sort_keys=True))
