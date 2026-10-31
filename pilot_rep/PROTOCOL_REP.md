# Zombie Facts — varied-phrasing replication protocol (pre-registered)

**Status:** package built and gate-verified offline on Oct 30, 2026.
**No model call has been made.** The run starts only on the author's explicit
approval of the cap in `PILOT_PROPOSAL_REP.md`.

## Question

The v2 pilot's reader effect — 6/48 raw zombies, all in the
direct→paraphrase chain, all answering v2 — rests on a single final-update
template. This replication asks whether the effect survives varied weak
phrasings or was a quirk of that one template.

## Design (everything else held constant vs v2)

- Same 8-session layout, same ~20k-token padding (measured band
  20,085–20,132 whitespace tokens), same distractor structure, same
  probes, same exact-value instruction, same model and decoding.
- **Raw arm only.** Retrieval and versioned arms do not test
  final-update phrasing, and v2 already measured them.
- First update always "direct" (clearly marked). The final update varies
  over 6 phrasings:
  - `weak_baseline` — the exact v2 paraphrase template (anchor).
  - `weak_aside`, `weak_hearsay`, `weak_parenthetical`,
    `weak_imperative` — four novel weak phrasings, all carrying entity +
    attribute + value with no "Update:" marker and no supersession verb
    (gate G5 enforces the ban list: update/replace/supersede/previous/
    archive/historical/earlier).
  - `direct` — strong-phrasing control (carries the "Update:" marker).
- **Proximity fixed to "none."** v2 showed the effect across proximities
  including none; the re-mention is not the question here, so fixing it
  isolates phrasing.
- 6 finals × 4 kinds × 2 replicates = **48 update scenarios** + 8
  no-update controls (2 per kind). Fresh seed 777029 (disjoint from
  spike 42, v1 90210, v2 777013). Per-template n = 8 action probes.
- Paired recall probes throughout, for pure/explained attribution.

## Primary outcome

Raw-arm zombie rate **by final phrasing**, with the v1/v2 dead split and
pure zombie attribution per phrasing.

## Pre-registered decision rule

- **Effect generalizes:** ≥ 2 of the 5 weak phrasings show ≥ 1 raw zombie
  (action), with at least one pure zombie overall → the weak-final
  effect is not a single-template quirk. Proceed to publication with the
  stronger claim.
- **Template-specific:** only `weak_baseline` shows zombies and all 4
  novel weak phrasings show 0 → do not generalize. Publish only the
  narrow claim (or park), and say so.
- **Phrasing is not the driver:** the `direct` control shows zombies at
  a similar rate to the weak phrasings → position/length, not phrasing,
  explains v2's chain-A cell. Reinterpret; do not publish a phrasing
  claim.
- **Fails to replicate:** 0 zombies everywhere → v2's chain-A cell does
  not reproduce at this n. Revise the v2 interpretation before any
  publication claim.

## Power, stated plainly

Per-template n = 8 action probes. This is a **screen for
presence/absence across templates**, not a precise rate estimate: a
template showing 0/8 could still carry a small true rate, and a
template showing 1–2/8 is evidence of presence, not a measurement of
its size. The decision rule is written at that level on purpose.

## Guards (carried over)

- Floor guard: raw correct rate below 50% overall → suspect rendering,
  inspect before interpreting.
- Controls 100% expected; any control miss is reported, not averaged away.
- Truncated responses excluded and counted, never silently scored.

## Run shape

- Model: `muse-spark-1.3-contributor`, temperature 0, reasoning low,
  output caps 1024 — same as v1/v2.
- Stage A: 8 calibration calls (baseline action+recall, aside
  action+recall, direct-control action, hearsay action, parenthetical
  action, control action). Stage B: remaining 96.
- **Calibration stop rule:** if Stage A actuals project the full run
  above the approved cap, STOP and re-ask. No silent scope cut, no cap
  overrun.

## Files

- `generator_rep.py` — reuses pilot_v2's generator (untouched) with the
  new final styles patched in
- `build_prompts_rep.py` → `prompts_rep.jsonl`, `gold_rep.jsonl`,
  `manifest_rep.json`
- `score_rep.py` — offline scorer (dead split, pure attribution,
  by-final breakdown via the chain field)
- `run_pilot_rep.py` — cap-enforcing runner (NOT run)
- `run_gates_rep.py` → `results/gates_rep.json` — 10 gates, all passing
