# Release checklist

Steps 1–3 are done (Oct 30, 2026). On Oct 31, 2026 the history was
rewritten to a single clean commit: spend figures and first-name
approval notes were removed from the tree (price-fact values, which are
benchmark content, and bare numeric constants in runner code, which are
functional, remain). Step 4 is re-verification after that rewrite; step
5 still needs its own explicit go.

## 1. Identity (DECIDED Oct 30, 2026)

For repos, publishing goes under the author's GitHub account
(`jurayh`), following the pattern of the existing research repos. This
settles the repo question only; the standing studio-name decision still
governs store-distributed apps and games, where the entity choice is
separate. The package itself contains no personal names, addresses,
emails, or credentials — only first-name approval notes in the pilot
docs. The announcement draft's "[repo link]" becomes
https://github.com/jurayh/zombie-facts once the repo exists.

## 2. License (done)

MIT, holder `jurayh`, shipped as `LICENSE`.

## 3. Create the repo (done Oct 30, 2026)

Created in the web UI as public `jurayh/zombie-facts`, empty (no README,
.gitignore, or license added by GitHub), then seeded and pushed from
this package (see step 4).

## 4. Verify after push

- Repo tree matches this package (spot-check: README, FINDINGS_
  CONSOLIDATED, REPRODUCE, pilot_v2/PILOT_FINDINGS_V2.md).
- `python3 -m unittest discover -s tests` passes from a clean clone.
- No file contains a credential, token, or personal address (grep for
  `api_key`, `Bearer`, personal names before pushing).

## 5. Announce (separate explicit go)

`ANNOUNCEMENT_DRAFT.md` is a draft only. Posting it anywhere — and
choosing the account and venue — needs its own explicit approval after
the repo is live. Do not post from this package's preparation alone.
