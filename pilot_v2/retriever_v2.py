"""TF-IDF retriever for the v2 pilot: a closer proxy for a production
embedding retriever than v1's canonical-phrasing keyword ranker.

Chunks are every fact-bearing statement in the transcript (target facts,
distractor facts, updates, re-mentions). The query is the probe text.
Score = TF-IDF cosine similarity over lowercase word tokens with a small
stopword list. No version awareness: the store does not know which chunk
is current.

Tie-break (stated parameter, and the honest limit of this proxy): when the
top two chunks score within 0.02, the earliest-indexed chunk wins — the
behaviour of a similarity index with no version signal, where near-duplicate
versions are effectively tied and insertion order decides. The score margin
is recorded alongside every choice so the analysis can separate clear wins
from ties.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "for", "of", "to", "in", "on", "at",
    "and", "or", "by", "with", "as", "it", "its", "this", "that",
}
TIE_EPSILON = 0.02


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def retrieve(chunks: list, query: str):
    """Return (chunk, top_score, margin) for the top-ranked chunk."""
    docs = [_tokens(c.text) for c in chunks]
    n = len(docs)
    df = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def vec(tokens):
        counts = Counter(tokens)
        v = {t: counts[t] * idf.get(t, math.log(n + 1) + 1.0) for t in counts}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    qv = vec(_tokens(query))
    scored = []
    for idx, (chunk, d) in enumerate(zip(chunks, docs)):
        dv = vec(d)
        score = sum(qv.get(t, 0.0) * dv.get(t, 0.0) for t in qv)
        scored.append((score, idx, chunk))
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_score = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    margin = top_score - second
    if margin < TIE_EPSILON:
        # Near-tie: earliest-indexed chunk among those within epsilon of top.
        tied = [s for s in scored if top_score - s[0] < TIE_EPSILON]
        tied.sort(key=lambda x: x[1])
        return tied[0][2], tied[0][0], margin
    return scored[0][2], top_score, margin
