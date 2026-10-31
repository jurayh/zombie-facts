"""Reference agents: deterministic readers over a Presentation.

The headline agent is NearestMentionAgent, a direct operationalisation of
the claim this benchmark exists to test: *when memory contradicts itself,
the version nearest the probe wins.* It also has style-dependent encoding
misses for the update event itself (a tool result the agent merely sees is
encoded less reliably than a direct statement). Those miss rates are agent
parameters, stated here; a live model arm replaces this reader wholesale.

OracleAgent and PrimacyAgent are sanity instruments, not contestants:
the oracle must score a zombie rate of 0 and the primacy reader (first
mention wins) a zombie rate of 1 on raw transcripts. If either fails, the
scorer, not the phenomenon, is broken.
"""
from __future__ import annotations

from .arms import Presentation
from .generator import Scenario, stable_unit

AGENT_MISS = {"direct": 0.00, "paraphrase": 0.35, "document": 0.20, "tool_result": 0.60}


class NearestMentionAgent:
    name = "nearest_mention"

    def _encoded(self, seed: int, scenario: Scenario, cand) -> bool:
        if cand.kind != "update":
            return True  # plants and re-mentions are salient mentions
        miss = AGENT_MISS[cand.style]
        return stable_unit(seed, scenario.scenario_id, "agent_miss", cand.event_id) >= miss

    def answer(self, seed: int, scenario: Scenario, pres: Presentation,
               ground_truth: str | None = None) -> str | None:
        if pres.mode == "top1":
            # A RAG-style reader acts on the retrieved chunk it was handed.
            return pres.candidates[0].value if pres.candidates else None
        chosen: str | None = None
        for cand in pres.candidates:
            if self._encoded(seed, scenario, cand):
                chosen = cand.value  # nearest (last presented) encoded mention wins
        return chosen


class OracleAgent:
    name = "oracle"

    def answer(self, seed, scenario, pres, ground_truth=None):
        return ground_truth


class PrimacyAgent:
    """First encoded mention wins — the maximal-zombie reader."""
    name = "primacy"

    def answer(self, seed, scenario, pres, ground_truth=None):
        if pres.mode == "top1":
            return pres.candidates[0].value if pres.candidates else None
        for cand in pres.candidates:
            return cand.value
        return None
