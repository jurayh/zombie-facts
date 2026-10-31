"""Synthetic world generator for the Zombie Facts spike.

Every scenario is a short multi-session history about ONE fact with a known
lifecycle:

    session 0  plant v1 (canonical direct statement)
    sessions 1-2  filler (unrelated chatter, no fact content)
    session 3  UPDATE to v2, in one of four styles (or no update: control)
    session 4  filler
    session 5  proximity manipulation (or filler, when proximity == "none")
    probe      action probe (use the fact) / paired v2-recall probe

Update styles
-------------
direct      explicit "is now X, replaces the previous" statement
paraphrase  indirect, in-passing wording of the same change
document    a document (amendment / notice) the agent processes
tool_result a tool/lookup result the agent merely sees

Proximity conditions
--------------------
dead_near  after the update, a *historical* archive note re-mentions v1
           ("earlier, it was ..."), placing the dead fact nearest the probe
live_near  after the update, a confirmation re-states v2, placing the live
           fact nearest the probe
none       no re-mention; the update is the last fact-bearing event

Ground truth is structural: scenario.current_value is always the value an
agent SHOULD act on, scenario.dead_value the superseded one (for no-update
controls the two coincide and the current value is v1).
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

STYLES = ("direct", "paraphrase", "document", "tool_result")
PROXIMITIES = ("dead_near", "live_near", "none")
KINDS = ("address", "price", "schedule", "rule")


def stable_unit(*parts: object) -> float:
    """Deterministic pseudo-random float in [0, 1) from the given parts."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16) / float(16**12)


@dataclass
class Event:
    event_id: str
    session: int
    kind: str  # plant | update | filler | remention_dead | remention_live
    text: str
    style: str | None = None
    value: str | None = None  # structured value, for fact-bearing events

    @property
    def fact_bearing(self) -> bool:
        return self.kind in ("plant", "update", "remention_dead", "remention_live")


@dataclass
class Scenario:
    scenario_id: str
    kind: str
    entity: str
    attribute: str
    v1: str
    v2: str | None  # None for no-update controls
    update_style: str | None
    proximity: str
    events: list[Event] = field(default_factory=list)

    @property
    def has_update(self) -> bool:
        return self.v2 is not None

    @property
    def current_value(self) -> str:
        return self.v2 if self.has_update else self.v1

    @property
    def dead_value(self) -> str:
        return self.v1 if self.has_update else self.v1  # v1 is only "dead" with an update

    @property
    def fact_key(self) -> str:
        return f"{self.entity}|{self.attribute}"

    def action_probe(self) -> str:
        verb = {
            "address": f"Address the parcel for {self.entity}",
            "price": f"Quote a customer the price of {self.entity}",
            "schedule": f"Plan around {self.entity}",
            "rule": f"Handle a pickup under {self.entity}",
        }[self.kind]
        return f"{verb}, using the {self.attribute} currently on file. What value do you use?"

    def recall_probe(self) -> str:
        return f"What is the current {self.attribute} for {self.entity}?"


# --------------------------------------------------------------------------
# Value pools per fact kind
# --------------------------------------------------------------------------

_PEOPLE = ["Mina", "Theo", "Ana", "Ravi", "Sofia", "Jonas", "Priya", "Marco", "Lena", "Omar"]
_PRODUCTS = ["trail mug", "field notebook", "canvas tote", "desk lamp", "wool scarf", "enamel pot"]
_ACTIVITIES = ["choir rehearsal", "team standup", "dentist appointment", "book club"]
_SERVICES = ["bakery pickup", "library hold", "bike repair", "flower delivery"]

_STREETS = ["Willow St", "Oak Ave", "Cedar Rd", "Maple St", "Birch Ln", "Elm St", "Juniper Way", "Alder Ct"]
_DAYS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays"]
_TIMES = ["09:00", "10:30", "13:00", "15:30", "17:45"]
_RULES = [
    "collect from the side window only",
    "text on arrival and wait outside",
    "knock twice and leave the parcel by the bench",
    "hand the parcel to the front desk, never leave it",
    "use the rear entrance and ring once",
    "wait at the counter until your name is called",
]

_FILLERS = [
    "Session note: the weather chat ran long; nothing was decided.",
    "Session note: a joke about trains, then small talk about lunch spots.",
    "Session note: someone shared a photo of a dog in a hat.",
    "Session note: scheduling trivia and a story about a lost umbrella.",
    "Session note: a debate about coffee versus tea, unresolved.",
    "Session note: holiday plans were mentioned in passing.",
]


def _values_for(kind: str, rng: random.Random) -> tuple[str, str, str]:
    """Return (entity, v1, v2) with v1 != v2."""
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
    v1, v2 = rng.sample(pool, 2)
    return entity, v1, v2


_ATTRIBUTE = {
    "address": "delivery address",
    "price": "price",
    "schedule": "scheduled time",
    "rule": "pickup rule",
}


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


def make_scenario(seed: int, scenario_id: str, kind: str, update_style: str | None,
                  proximity: str, replicate: int) -> Scenario:
    rng = random.Random(f"{seed}|{scenario_id}")
    entity, v1, v2_pick = _values_for(kind, rng)
    attribute = _ATTRIBUTE[kind]
    has_update = update_style is not None
    v2 = v2_pick if has_update else None
    current = v2 if has_update else v1

    events: list[Event] = []
    events.append(Event(f"{scenario_id}-plant", 0, "plant",
                        f"Record: {entity} — the {attribute} is {v1}.", style="direct", value=v1))
    for i in (1, 2):
        events.append(Event(f"{scenario_id}-f{i}", i, "filler", _FILLERS[(replicate + i) % len(_FILLERS)]))
    if has_update:
        events.append(Event(f"{scenario_id}-update", 3, "update",
                            _update_text(update_style, entity, attribute, v2),
                            style=update_style, value=v2))
    else:
        events.append(Event(f"{scenario_id}-f3", 3, "filler", _FILLERS[(replicate + 3) % len(_FILLERS)]))
    events.append(Event(f"{scenario_id}-f4", 4, "filler", _FILLERS[(replicate + 4) % len(_FILLERS)]))
    if proximity == "dead_near" and has_update:
        events.append(Event(f"{scenario_id}-rem", 5, "remention_dead",
                            f"Archive note (historical): earlier, {entity} — the {attribute} was {v1}.",
                            style="historical", value=v1))
    elif proximity == "live_near" and has_update:
        events.append(Event(f"{scenario_id}-rem", 5, "remention_live",
                            f"Confirmation: {entity} — the {attribute} is currently {current}.",
                            style="direct", value=current))
    else:
        events.append(Event(f"{scenario_id}-f5", 5, "filler", _FILLERS[(replicate + 5) % len(_FILLERS)]))

    return Scenario(scenario_id=scenario_id, kind=kind, entity=entity, attribute=attribute,
                    v1=v1, v2=v2, update_style=update_style, proximity=proximity, events=events)


def generate_dataset(seed: int = 42, replicates: int = 5) -> list[Scenario]:
    """Balanced factorial dataset.

    Update scenarios: 4 kinds x 4 styles x 3 proximities x `replicates` = 240
    at the default. No-update controls: 4 kinds x 10 = 40.
    """
    scenarios: list[Scenario] = []
    n = 0
    for kind in KINDS:
        for style in STYLES:
            for prox in PROXIMITIES:
                for r in range(replicates):
                    sid = f"upd-{n:04d}"
                    scenarios.append(make_scenario(seed, sid, kind, style, prox, r))
                    n += 1
    for kind in KINDS:
        for r in range(10):
            sid = f"ctl-{kind}-{r:02d}"
            scenarios.append(make_scenario(seed, sid, kind, None, "none", r))
    return scenarios
