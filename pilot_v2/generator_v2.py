"""Hard-regime scenario generator for the Zombie Facts v2 pilot.

What changes vs v1 (each change removes a cue the v1 live model leaned on,
or a scale limit of the v1 pilot):

  * Chained updates: v1 -> v2 -> v3. Ground truth is v3; v1 and v2 are both
    dead values, tracked separately (answering v2, the most recent dead
    value, is a different signature from answering v1).
  * Unlabelled re-mentions: the dead-near conditions restate an old value
    in passing ("a message in the thread mentions ... in passing") with NO
    archive / historical / earlier / superseded wording anywhere in the
    re-mention. v1's dead-near note was explicitly marked historical, and
    the live model used that cue.
  * Distractor facts: each history interleaves facts about other entities
    (some themselves updated), so the target fact is buried among many
    competing facts instead of sitting nearly alone.
  * Long histories: transcripts padded to ~20,000 whitespace tokens
    (10x the v1 pilot's ~2,000).

Session layout (identical session count for every scenario, so probe
distance is held constant across proximity conditions):
  S0  plant target v1
  S1  distractors + filler
  S2  update to v2 (chain style 1)
  S3  distractors (one updated) + filler
  S4  update to v3 (chain style 2)
  S5  distractors + filler
  S6  proximity re-mention, or filler when proximity == "none"
  S7  filler (no facts)
Probe: action probe (use the fact) / paired recall probe (same history
with S6 replaced by filler, direct current-value question).
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

CHAINS = (
    ("direct", "paraphrase"),
    ("paraphrase", "tool_result"),
    ("document", "direct"),
    ("tool_result", "document"),
)
PROXIMITIES = ("dead_old", "dead_recent", "live_near", "none")
KINDS = ("address", "price", "schedule", "rule")
TARGET_TOKENS = 20000
TOKEN_LO, TOKEN_HI = 19000, 21000

_PEOPLE = ["Mina", "Theo", "Ana", "Ravi", "Sofia", "Jonas", "Priya", "Marco", "Lena", "Omar",
           "Nina", "Kofi", "Elsa", "Dario", "Ines", "Tomas"]
_PRODUCTS = ["trail mug", "field notebook", "canvas tote", "desk lamp", "wool scarf", "enamel pot",
             "steel bottle", "linen apron"]
_ACTIVITIES = ["choir rehearsal", "team standup", "dentist appointment", "book club",
               "yoga class", "repair workshop"]
_SERVICES = ["bakery pickup", "library hold", "bike repair", "flower delivery",
             "parcel depot", "dry cleaning"]
_STREETS = ["Willow St", "Oak Ave", "Cedar Rd", "Maple St", "Birch Ln", "Elm St",
            "Juniper Way", "Alder Ct", "Poplar Dr", "Chestnut Blvd"]
_DAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays"]
_TIMES = ["09:00", "10:30", "13:00", "15:30", "17:45"]
_RULES = [
    "collect from the side window only",
    "text on arrival and wait outside",
    "knock twice and leave the parcel by the bench",
    "hand the parcel to the front desk, never leave it",
    "use the rear entrance and ring once",
    "wait at the counter until your name is called",
    "leave the parcel with the neighbour upstairs",
    "sign at the door and take a photo of the receipt",
]
_ATTRIBUTE = {"address": "delivery address", "price": "price",
              "schedule": "scheduled time", "rule": "pickup rule"}

_FILLER_SENTENCES = [
    "The morning conversation drifted to office plants and which ones survive low light.",
    "Someone described a long train ride through farmland and small towns.",
    "There was a debate about whether soup counts as a meal on its own.",
    "A story about a neighbour who collects postcards from strangers came up again.",
    "The group traded tips for keeping herbs alive on a windowsill.",
    "Talk turned to favourite walking routes and the quiet streets after rain.",
    "Someone recalled a school play with cardboard trees and a painted moon.",
    "There was gentle disagreement about the best way to brew loose leaf tea.",
    "An anecdote about a lost umbrella on a windy pier made the rounds.",
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
    "An anecdote about learning to juggle with oranges came up.",
    "The conversation drifted to winter scarves and lost gloves.",
    "Someone described a tiny museum devoted to door knockers.",
    "Talk turned to picnic blankets and the etiquette of sharing shade.",
    "There was a story about a dog that waits for the mail every morning.",
    "The group traded memories of school lunches and traded snacks.",
    "Someone mentioned a choir that rehearses in a parking garage for the echo.",
]


def ws_tokens(text: str) -> int:
    return len(text.split())


def _update_text(style: str, entity: str, attribute: str, value: str) -> str:
    if style == "direct":
        return f"Update: {entity} — the {attribute} is now {value}. This replaces the previous {attribute}."
    if style == "paraphrase":
        return (f"Someone mentioned in passing that things have changed for {entity}; "
                f"these days the {attribute} is {value}, not what it used to be.")
    if style == "document":
        return (f"[Document processed: amendment for {entity}] Item: {attribute}. "
                f"Entered value: {value}. (This document supersedes the earlier entry.)")
    if style == "tool_result":
        return f"[Tool result: lookup for {entity}] {attribute}: {value}"
    raise ValueError(style)  # pragma: no cover


@dataclass
class Event:
    event_id: str
    session: int
    kind: str  # plant | update | filler | distractor | remention_dead_old |
               # remention_dead_recent | remention_live
    text: str
    style: str | None = None
    value: str | None = None
    entity: str | None = None
    attribute: str | None = None

    @property
    def fact_bearing(self) -> bool:
        return self.kind in ("plant", "update", "distractor",
                             "remention_dead_old", "remention_dead_recent", "remention_live")


@dataclass
class Scenario:
    scenario_id: str
    kind: str
    entity: str
    attribute: str
    v1: str
    v2: str
    v3: str
    chain: tuple[str, str]
    proximity: str
    events: list[Event] = field(default_factory=list)

    @property
    def has_update(self) -> bool:
        return self.chain[0] != "none"

    @property
    def current_value(self) -> str:
        return self.v3

    @property
    def dead_values(self) -> list[str]:
        return [self.v1, self.v2]

    def action_probe(self) -> str:
        verb = {"address": f"Address the parcel for {self.entity}",
                "price": f"Quote a customer the price of {self.entity}",
                "schedule": f"Plan around {self.entity}",
                "rule": f"Handle a pickup under {self.entity}"}[self.kind]
        return f"{verb}, using the {self.attribute} currently on file. What value do you use?"

    def recall_probe(self) -> str:
        return f"What is the current {self.attribute} for {self.entity}?"


def _values_for(kind: str, rng: random.Random) -> tuple[str, str, str, str]:
    if kind == "address":
        entity = rng.choice(_PEOPLE)
        pool = [f"{rng.randrange(10, 900)} {s}" for s in _STREETS]
    elif kind == "price":
        entity = rng.choice(_PRODUCTS)
        pool = [f"${n}" for n in range(8, 60)]
    elif kind == "schedule":
        entity = rng.choice(_ACTIVITIES)
        pool = [f"{d} at {t}" for d in _DAYS for t in _TIMES]
    elif kind == "rule":
        entity = rng.choice(_SERVICES)
        pool = list(_RULES)
    else:  # pragma: no cover
        raise ValueError(kind)
    v1, v2, v3 = rng.sample(pool, 3)
    return entity, v1, v2, v3


def _filler(seed_key: str, want_tokens: int) -> str:
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


def _distractor_events(sid: str, session: int, rng: random.Random, used: set,
                       target_entity: str, n: int, allow_update: bool,
                       forbidden: set | None = None) -> list[Event]:
    forbidden = forbidden or set()
    events: list[Event] = []
    for j in range(n):
        for _ in range(40):  # find an unused entity with non-colliding values
            kind = rng.choice(KINDS)
            entity, v1, v2, _v3 = _values_for(kind, rng)
            if (entity != target_entity and entity not in used
                    and v1 not in forbidden and v2 not in forbidden):
                break
        else:  # pragma: no cover
            continue
        used.add(entity)
        attribute = _ATTRIBUTE[kind]
        events.append(Event(f"{sid}-d{session}-{j}", session, "distractor",
                            f"Record: {entity} — the {attribute} is {v1}.",
                            style="direct", value=v1, entity=entity, attribute=attribute))
        if allow_update and rng.random() < 0.5:
            events.append(Event(f"{sid}-d{session}-{j}u", session, "distractor",
                                _update_text(rng.choice(("direct", "paraphrase")), entity, attribute, v2),
                                style="direct", value=v2, entity=entity, attribute=attribute))
    return events


def make_scenario(seed: int, scenario_id: str, kind: str, chain: tuple[str, str],
                  proximity: str, replicate: int) -> Scenario:
    rng = random.Random(f"{seed}|{scenario_id}")
    entity, v1, v2, v3 = _values_for(kind, rng)
    attribute = _ATTRIBUTE[kind]
    used = {entity}
    events: list[Event] = []
    events.append(Event(f"{scenario_id}-plant", 0, "plant",
                        f"Record: {entity} — the {attribute} is {v1}.",
                        style="direct", value=v1, entity=entity, attribute=attribute))
    events += _distractor_events(scenario_id, 1, rng, used, entity, 3, allow_update=False, forbidden={v1, v2, v3})
    events.append(Event(f"{scenario_id}-f1", 1, "filler", ""))
    events.append(Event(f"{scenario_id}-upd2", 2, "update",
                        _update_text(chain[0], entity, attribute, v2),
                        style=chain[0], value=v2, entity=entity, attribute=attribute))
    events += _distractor_events(scenario_id, 3, rng, used, entity, 3, allow_update=True, forbidden={v1, v2, v3})
    events.append(Event(f"{scenario_id}-f3", 3, "filler", ""))
    events.append(Event(f"{scenario_id}-upd3", 4, "update",
                        _update_text(chain[1], entity, attribute, v3),
                        style=chain[1], value=v3, entity=entity, attribute=attribute))
    events += _distractor_events(scenario_id, 5, rng, used, entity, 3, allow_update=False, forbidden={v1, v2, v3})
    events.append(Event(f"{scenario_id}-f5", 5, "filler", ""))
    if proximity == "dead_old":
        events.append(Event(f"{scenario_id}-rem", 6, "remention_dead_old",
                            f"A message in the thread mentions {entity}'s {attribute} as {v1} in passing.",
                            style="unlabelled", value=v1, entity=entity, attribute=attribute))
    elif proximity == "dead_recent":
        events.append(Event(f"{scenario_id}-rem", 6, "remention_dead_recent",
                            f"A message in the thread mentions {entity}'s {attribute} as {v2} in passing.",
                            style="unlabelled", value=v2, entity=entity, attribute=attribute))
    elif proximity == "live_near":
        events.append(Event(f"{scenario_id}-rem", 6, "remention_live",
                            f"Confirmation: {entity} — the {attribute} is currently {v3}.",
                            style="direct", value=v3, entity=entity, attribute=attribute))
    else:
        events.append(Event(f"{scenario_id}-f6", 6, "filler", ""))
    events.append(Event(f"{scenario_id}-f7", 7, "filler", ""))
    return Scenario(scenario_id=scenario_id, kind=kind, entity=entity, attribute=attribute,
                    v1=v1, v2=v2, v3=v3, chain=chain, proximity=proximity, events=events)


def padded_transcript(scenario: Scenario, strip_remention: bool) -> str:
    """Render the scenario history padded to ~20k whitespace tokens."""
    events = [e for e in scenario.events
              if not (strip_remention and e.kind in ("remention_dead_old",
                                                     "remention_dead_recent", "remention_live"))]
    base = sum(ws_tokens(e.text) for e in events)
    filler_events = [e for e in events if e.kind == "filler"]
    need = max(0, TARGET_TOKENS - base)
    per_slot = need // max(1, len(filler_events))
    blocks: list[str] = []
    for e in events:
        if e.kind == "filler":
            text = _filler(f"{scenario.scenario_id}|s{e.session}|strip{strip_remention}", per_slot)
            blocks.append(f"Session {e.session} notes: {text}")
        else:
            blocks.append(f"Session {e.session}: {e.text}")
    return "\n".join(blocks)


def generate_dataset(seed: int, replicates: int = 3) -> list[Scenario]:
    """48 update scenarios (4 chains x 4 proximities x 3 reps) + 12 controls."""
    scenarios: list[Scenario] = []
    n = 0
    for ci, chain in enumerate(CHAINS):
        for pi, prox in enumerate(PROXIMITIES):
            for r in range(replicates):
                kind = KINDS[(r + ci + pi) % len(KINDS)]
                sid = f"pilot2-upd-{n:03d}"
                scenarios.append(make_scenario(seed, sid, kind, chain, prox, r))
                n += 1
    for ki, kind in enumerate(KINDS):
        for r in range(3):
            sid = f"pilot2-ctl-{ki * 3 + r:03d}"
            # Control: single version only. Reuse make_scenario then drop the
            # chain: rebuild a control scenario by hand from its plant.
            base = make_scenario(seed, sid, kind, CHAINS[0], "none", r)
            ctl_events = [e for e in base.events
                          if e.kind not in ("update", "remention_dead_old",
                                            "remention_dead_recent", "remention_live")]
            ctl = Scenario(scenario_id=sid, kind=kind, entity=base.entity,
                           attribute=base.attribute, v1=base.v1, v2=base.v1, v3=base.v1,
                           chain=("none", "none"), proximity="none", events=ctl_events)
            scenarios.append(ctl)
    return scenarios
