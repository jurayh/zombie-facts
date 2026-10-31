"""Memory arms: four architectures over the same scenario history.

Each arm ingests the scenario's events and, at probe time, returns a
Presentation: an ordered list of Candidate values the agent may act on,
plus a mode:

  nearest  candidates are presented in order; the last one sits nearest the
           probe (this is the proximity the HN claim is about)
  top1     a ranked retrieval result; the agent acts on the top candidate

The arms are *reference implementations*, deliberately simple and fully
deterministic. Their extraction behaviours are parameters, stated here so a
reader can disagree with them: what the spike tests is the harness and the
metric, and whether architectures CAN separate under a stated reader model
(see agents.py). Real systems replace these classes; live LLM readers
replace the reference agent.

Extraction model (store-side): when an update arrives, a store "registers"
it with a style-dependent probability (stable hash of seed/scenario/arm/
event, so runs are byte-identical). Direct statements are easiest to
register, tool results the hardest for a prose summariser, easiest for a
structured versioned store, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .generator import Event, Scenario, stable_unit

SUMMARY_EXTRACT = {"direct": 0.95, "paraphrase": 0.60, "document": 0.80, "tool_result": 0.30}
VERSIONED_EXTRACT = {"direct": 1.00, "paraphrase": 0.85, "document": 0.95, "tool_result": 0.70}
LIVE_CONFIRM_EXTRACT = {"summary": 0.95, "versioned": 0.95}
# Retrieval chunk scores: every fact chunk matches entity+attribute (base 2).
# The differentiator is phrasing match with a canonical current-value probe:
# a plant and a direct update use the canonical phrasing; a paraphrase or a
# tool dump does not, so the canonical dead chunk can outrank the live one.
CANONICAL_BONUS = {"plant": 2.0, "direct": 2.0, "paraphrase": 0.5,
                   "document": 1.0, "tool_result": 0.5, "historical": 0.5}
RECENCY_PER_SESSION = 0.05


@dataclass
class Candidate:
    value: str
    event_id: str
    kind: str
    style: str | None
    session: int
    score: float | None = None


@dataclass
class Presentation:
    candidates: list[Candidate] = field(default_factory=list)
    mode: str = "nearest"  # nearest | top1


def _extracted(seed: int, scenario: Scenario, arm: str, event: Event, prob: float) -> bool:
    return stable_unit(seed, scenario.scenario_id, arm, event.event_id) < prob


class RawTranscriptArm:
    """Keeps everything verbatim; presents fact events chronologically."""
    name = "raw_transcript"

    def present(self, seed: int, scenario: Scenario, events: list[Event]) -> Presentation:
        cands = [Candidate(e.value, e.event_id, e.kind, e.style, e.session)
                 for e in events if e.fact_bearing]
        return Presentation(cands, mode="nearest")


class SummaryArm:
    """A prose summariser keeps one note per fact key.

    Historical re-mentions are recognised as history and ignored; an update
    is folded into the note only if the summariser extracts it (style-
    dependent). A live confirmation is a direct statement and usually
    rescues a missed update. The presented candidate is the note itself
    (kind "note"), so the reader's event-encoding misses do not apply to
    it a second time.
    """
    name = "summary"

    def present(self, seed: int, scenario: Scenario, events: list[Event]) -> Presentation:
        note: Candidate | None = None
        for e in events:
            if e.kind == "plant":
                note = Candidate(e.value, e.event_id, "note", e.style, e.session)
            elif e.kind == "update":
                if _extracted(seed, scenario, self.name, e, SUMMARY_EXTRACT[e.style]):
                    note = Candidate(e.value, e.event_id, "note", e.style, e.session)
            elif e.kind == "remention_live":
                if _extracted(seed, scenario, self.name, e, LIVE_CONFIRM_EXTRACT[self.name]):
                    note = Candidate(e.value, e.event_id, "note", e.style, e.session)
            # remention_dead: summariser correctly treats it as history
        return Presentation([note] if note else [], mode="nearest")


class RetrievalArm:
    """Chunk store + ranked retrieval, no version awareness.

    Score = entity/attribute match (2, all fact chunks) + canonical-phrasing
    bonus + small recency term. The agent acts on the top-ranked chunk.
    """
    name = "retrieval"

    def present(self, seed: int, scenario: Scenario, events: list[Event]) -> Presentation:
        scored: list[Candidate] = []
        for e in events:
            if not e.fact_bearing:
                continue
            bonus_key = "plant" if e.kind == "plant" else e.style
            score = 2.0 + CANONICAL_BONUS[bonus_key] + RECENCY_PER_SESSION * e.session
            scored.append(Candidate(e.value, e.event_id, e.kind, e.style, e.session, score=score))
        scored.sort(key=lambda c: (-c.score, c.event_id))
        return Presentation(scored[:1], mode="top1")


class VersionedArm:
    """Structured store with supersession links.

    An update that is registered replaces the current node and links the old
    one as superseded; queries return only the current node. Historical
    re-mentions never create versions. A live confirmation can register a
    previously missed update. The presented candidate is the current
    record itself (kind "record"), not the original update event.
    """
    name = "versioned"

    def present(self, seed: int, scenario: Scenario, events: list[Event]) -> Presentation:
        current: Candidate | None = None
        for e in events:
            if e.kind == "plant":
                current = Candidate(e.value, e.event_id, "record", e.style, e.session)
            elif e.kind == "update":
                if _extracted(seed, scenario, self.name, e, VERSIONED_EXTRACT[e.style]):
                    current = Candidate(e.value, e.event_id, "record", e.style, e.session)
            elif e.kind == "remention_live":
                if _extracted(seed, scenario, self.name, e, LIVE_CONFIRM_EXTRACT[self.name]):
                    current = Candidate(e.value, e.event_id, "record", e.style, e.session)
            # remention_dead: marked historical at ingest; no version created
        return Presentation([current] if current else [], mode="nearest")


ARMS = {
    "raw_transcript": RawTranscriptArm,
    "summary": SummaryArm,
    "retrieval": RetrievalArm,
    "versioned": VersionedArm,
}
