from app.domain.chunk import Chunk
from app.domain.retrieval import RetrievalPlan
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql


def search_dense(kb_id: str, plan: RetrievalPlan) -> list[Chunk]:
    """Dense-only pgvector cosine search, unioned across sub-queries, deduped by
    chunk_id. Hybrid+rerank lands in Step 3 — this is the P5 floor it degrades to."""
    seen: dict[str, Chunk] = {}
    with get_session() as session:
        for query in plan.sub_queries:
            qvec = embedding_to_sql(embed(query))
            rows = session.execute(
                """SELECT chunk_id, kb_id, doc_id, lower(block_span) AS lo, upper(block_span) - 1 AS hi,
                          text, order_confidence, degraded
                   FROM chunk WHERE kb_id = :kb
                   ORDER BY embedding <=> (:qvec)::vector LIMIT :k""",
                {"kb": kb_id, "qvec": qvec, "k": plan.k_per_query},
            ).mappings()
            for row in rows:
                if row["chunk_id"] in seen:
                    continue
                seen[row["chunk_id"]] = Chunk(
                    chunk_id=row["chunk_id"],
                    kb_id=row["kb_id"],
                    doc_id=row["doc_id"],
                    block_span=(row["lo"], row["hi"]),
                    text=row["text"],
                    order_confidence=row["order_confidence"],
                    degraded=row["degraded"],
                )
    return list(seen.values())
