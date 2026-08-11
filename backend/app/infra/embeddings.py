import hashlib

from app.infra.settings import llm_settings


def embed(text: str) -> list[float]:
    """Real OpenAI embeddings when a key is configured; otherwise a deterministic,
    content-hashed pseudo-embedding so ingest/retrieval are fully testable offline.
    Same content_hash discipline as everything else (P6): same text -> same vector."""
    if llm_settings.openai_api_key:
        return _embed_openai(text)
    return _embed_fake(text)


def _embed_openai(text: str) -> list[float]:
    from openai import OpenAI

    client = OpenAI(api_key=llm_settings.openai_api_key)
    resp = client.embeddings.create(model=llm_settings.embedding_model, input=text)
    return resp.data[0].embedding


def _embed_fake(text: str) -> list[float]:
    dim = llm_settings.embedding_dim
    out: list[float] = []
    counter = 0
    while len(out) < dim:
        digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
        out.extend(b / 255.0 - 0.5 for b in digest)
        counter += 1
    return out[:dim]


def embedding_to_sql(embedding: list[float]) -> str:
    """pgvector literal, e.g. '[0.1,0.2,...]', for a ::vector cast in raw SQL."""
    return "[" + ",".join(repr(x) for x in embedding) + "]"
