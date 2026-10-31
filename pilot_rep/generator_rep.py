"""Varied-phrasing replication generator for Zombie Facts.

Question: does the v2 chain-A reader effect (final update in weak,
passing-mention phrasing missed; reader falls back to the last
clearly-marked update) survive varied weak phrasings, or was it a quirk
of the single v2 paraphrase template?

Design (everything else held constant vs v2):
  * Same 8-session layout, same ~20k-token padding, same distractor
    structure, same probes, same raw arm only.
  * First update always "direct" (clearly marked). The FINAL update
    varies over 6 phrasings: the v2 baseline paraphrase, 4 novel weak
    phrasings, and a direct control.
  * Proximity fixed to "none": v2 already showed the effect across
    proximities including none, and the re-mention is not the question
    here. Fixing it isolates phrasing.
  * 6 finals x 4 kinds x 2 replicates = 48 update scenarios + 8
    no-update controls (2 per kind).

Implementation: reuses pilot_v2's generator wholesale (same value pools,
filler, padding, distractor logic) via its make_scenario, with
_update_text monkeypatched to add the new final styles. The v2 module
itself is untouched, so the v2 corpus is unaffected.
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).parent
_V2 = _HERE.parent / "pilot_v2"
sys.path.insert(0, str(_V2))

import generator_v2 as gen2

REP_SEED = 777029
V2_SEED = 777013
V1_SEED = 90210
SPIKE_SEED = 42

# Weak phrasings: entity + attribute + value present, but NO "Update:"
# marker and NO supersession verb (update/replace/supersede/previous).
WEAK_TEMPLATES = {
    # Baseline: the exact v2 paraphrase template (comparability anchor).
    "weak_baseline": ("Someone mentioned in passing that things have changed "
                      "for {entity}; these days the {attribute} is {value}, "
                      "not what it used to be."),
    "weak_aside": ("By the way, {entity}'s {attribute} is {value} now, "
                   "in case that comes up."),
    "weak_hearsay": ("I heard someone say {entity} has {value} as the "
                     "{attribute} these days."),
    "weak_parenthetical": ("The note about {entity} (whose {attribute} is "
                           "{value}) was in the pile with the rest."),
    "weak_imperative": ("When you deal with {entity}, go with {value} "
                        "for the {attribute}."),
}
# Final styles in scenario order: 5 weak + direct control.
FINAL_STYLES = list(WEAK_TEMPLATES) + ["direct"]
KINDS = gen2.KINDS

_orig_update_text = gen2._update_text


def _patched_update_text(style, entity, attribute, value):
    if style in WEAK_TEMPLATES:
        return WEAK_TEMPLATES[style].format(entity=entity, attribute=attribute, value=value)
    return _orig_update_text(style, entity, attribute, value)


gen2._update_text = _patched_update_text


def generate_dataset(seed: int = REP_SEED) -> list:
    scenarios: list = []
    n = 0
    for fi, final in enumerate(FINAL_STYLES):
        for ki, kind in enumerate(KINDS):
            for r in range(2):
                sid = f"pilot3-upd-{n:03d}"
                scenarios.append(gen2.make_scenario(
                    seed, sid, kind, ("direct", final), "none", r))
                n += 1
    for ki, kind in enumerate(KINDS):
        for r in range(2):
            sid = f"pilot3-ctl-{ki * 2 + r:03d}"
            base = gen2.make_scenario(seed, sid, kind, ("direct", "weak_baseline"), "none", r)
            ctl_events = [e for e in base.events
                          if e.kind not in ("update", "remention_dead_old",
                                            "remention_dead_recent", "remention_live")]
            scenarios.append(gen2.Scenario(
                scenario_id=sid, kind=kind, entity=base.entity,
                attribute=base.attribute, v1=base.v1, v2=base.v1, v3=base.v1,
                chain=("none", "none"), proximity="none", events=ctl_events))
    return scenarios
