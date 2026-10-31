# Announcement draft — NOT POSTED

Post only on an explicit go, from the account chosen at release time
(see RELEASE_CHECKLIST.md for the identity decision).

---

Zombie Facts: a benchmark for the other memory failure.

Most memory evals grade recall. This one grades supersession: when a
fact gets replaced, does your agent act on the new value or the dead
one?

Three live runs, one model class:

- At 2k tokens with clearly marked updates, the reader was perfect.
  The failures were all in the store: version-blind retrieval handed
  the reader the dead value half the time.
- At 20k tokens with chained updates, the reader started failing too,
  but only when the final update arrived as a passing mention. It fell
  back to the last clearly marked update. Never to the oldest value.
- A replication across five weak phrasings confirmed it is not one
  template's quirk: hearsay and parenthetical updates were missed
  every time, while a directly marked update at the same position was
  never missed.

The benchmark is open source: generator, reference arms, protocols,
scores, and the offline core that reproduces the scripted results
exactly.

https://github.com/jurayh/zombie-facts

---

Shorter variant (for a post with a link):

Your agent remembers the old address perfectly. That is the problem.
Zombie Facts measures how often agents act on superseded facts, and
finds the failure hides in weak updates: a final change mentioned in
passing gets missed, and the agent falls back to the last clearly
marked version. Repo and findings: https://github.com/jurayh/zombie-facts
