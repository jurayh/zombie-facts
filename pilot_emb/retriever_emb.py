"""Cosine top-1 retriever over embedded fact-bearing chunks.

This mirrors retriever_v2.py's contract so embedding results are
directly comparable to the TF-IDF results: same chunk set, same query
texts, same tie rule (margin < TIE_EPSILON -> earliest index wins),
same recorded fields (chosen chunk, score, margin, tie flag).

The one deliberate difference: the tie rule here is over cosine scores
of real embeddings, not TF-IDF scores. The tie split is therefore the
headline comparison of this pilot: how much of the embedding retriever's
zombie rate is tie-driven versus clear-win-driven.
"""

from __future__ import annotations

import math

TIE_EPSILON = 0.02  # same value as the TF-IDF retriever, for comparability


def cosine(a, b):
    """Cosine similarity; both inputs are expected to be normalised."""
    return sum(x * y for x, y in zip(a, b))


def retrieve(chunk_ids, chunk_vecs, query_vec, epsilon=TIE_EPSILON):
    """Return the top-1 chunk and ranking diagnostics.

    Returns a dict with: chosen (chunk id), score (top cosine),
    second_score, margin, tie (bool: margin < epsilon), and the
    full ranking of (chunk_id, score) sorted by score desc, index asc.
    On a tie the earliest chunk in `chunk_ids` order wins, exactly as
    the TF-IDF retriever's index-order tie-break.
    """
    scored = [(cid, cosine(vec, query_vec))
              for cid, vec in zip(chunk_ids, chunk_vecs)]
    # Sort by score desc, then by original index asc: stable, and the
    # earliest index wins ties.
    ranked = sorted(enumerate(scored), key=lambda p: (-p[1][1], p[0]))
    top_idx, (top_id, top_score) = ranked[0]
    if len(ranked) > 1:
        second_score = ranked[1][1][1]
    else:
        second_score = 0.0
    margin = top_score - second_score
    tie = margin < epsilon
    if tie:
        # Earliest index among all chunks within epsilon of the top.
        tied = [i for i, (_, s) in enumerate(scored)
                if top_score - s < epsilon]
        chosen = chunk_ids[min(tied)]
        chosen_score = scored[min(tied)][1]
    else:
        chosen = top_id
        chosen_score = top_score
    return {
        "chosen": chosen,
        "score": chosen_score,
        "second_score": second_score,
        "margin": margin,
        "tie": tie,
        "ranking": [(cid, s) for _, (cid, s) in ranked],
    }
