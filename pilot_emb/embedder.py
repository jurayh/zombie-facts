"""Embedding backends for the Zombie Facts embedding-retriever pilot.

A backend is a function from a list of texts to a list of vectors
(list of lists of floats). All backends are expected to return
L2-normalised vectors, so cosine similarity is a dot product.

Backends:
  stub  -- deterministic hash-based pseudo-embeddings. TESTS AND GATES
           ONLY. These are not embeddings and must never be reported as
           results. The stub exists so the retriever, the stage-A
           marking, and the scorer can be validated at 0 without any
           model, download, or API key.
  local -- sentence-transformers on CPU (default model
           all-MiniLM-L6-v2, override with EMB_LOCAL_MODEL). no money cost;
           the cost is a one-time model download (~90 MB) and CPU time.
           Imported lazily so the rest of the package runs without the
           dependency installed.
  api   -- OpenAI-compatible embeddings endpoint (default
           https://api.openai.com/v1/embeddings, model from
           EMB_API_MODEL, key from EMB_API_KEY, URL from EMB_API_URL).
           This is the only backend that spends money; the runner
           enforces a cap on it before any call is made.

No backend is imported or contacted at module import time. Nothing in
this module makes a reader call; the reader stage is run_reader_emb.py.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request

STUB_DIM = 16

LOCAL_DEFAULT_MODEL = "all-MiniLM-L6-v2"
API_DEFAULT_URL = "https://api.openai.com/v1/embeddings"
API_DEFAULT_MODEL = "text-embedding-3-small"


def _normalise(vec):
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_stub(texts):
    """Deterministic pseudo-embeddings for tests/gates only.

    Each text is hashed token by token into 16 buckets; the result is
    normalised. Similar texts share tokens and therefore score higher,
    which is enough to exercise the retriever's ranking and tie logic,
    but these vectors carry no semantic information and are never a
    substitute for a real embedding backend.
    """
    out = []
    for text in texts:
        vec = [0.0] * STUB_DIM
        for tok in text.lower().split():
            h = int(hashlib.sha256(tok.encode()).hexdigest()[:8], 16)
            vec[h % STUB_DIM] += 1.0
        out.append(_normalise(vec))
    return out


def embed_local(texts, model=None):
    """sentence-transformers on CPU. No money cost; model download is run-time."""
    from sentence_transformers import SentenceTransformer

    name = model or os.environ.get("EMB_LOCAL_MODEL", LOCAL_DEFAULT_MODEL)
    model_obj = SentenceTransformer(name, device="cpu")
    vecs = model_obj.encode(texts, normalize_embeddings=True,
                            show_progress_bar=False)
    return [list(map(float, v)) for v in vecs]


def embed_api(texts, model=None, url=None, key=None, batch=100):
    """OpenAI-compatible embeddings endpoint, batched."""
    endpoint = url or os.environ.get("EMB_API_URL", API_DEFAULT_URL)
    model_id = model or os.environ.get("EMB_API_MODEL", API_DEFAULT_MODEL)
    api_key = key or os.environ.get("EMB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "API backend needs EMB_API_KEY (or an explicit key). "
            "No key is read from any other source.")
    out = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        payload = json.dumps({"model": model_id, "input": chunk}).encode()
        req = urllib.request.Request(
            endpoint, data=payload,
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
        rows = sorted(body["data"], key=lambda r: r["index"])
        for row in rows:
            out.append(_normalise([float(x) for x in row["embedding"]]))
    return out


BACKENDS = {"stub": embed_stub, "local": embed_local, "api": embed_api}


def embed_texts(texts, backend):
    """Embed `texts` with the named backend. Unknown backend -> error."""
    if backend not in BACKENDS:
        raise ValueError(f"unknown embedding backend: {backend!r} "
                         f"(expected one of {sorted(BACKENDS)})")
    return BACKENDS[backend](texts)
