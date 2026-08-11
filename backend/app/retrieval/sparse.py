from app.domain.chunk import Chunk
from app.domain.retrieval import RetrievalPlan
from app.infra.db import get_session


def search_sparse(kb_id: str, plan: RetrievalPlan) -> list[Chunk]:
    """Postgres full-text search over the generated tsv column (migration
    0005), unioned across sub-queries, deduped by chunk_id -- same shape as
    search_dense so hybrid.py can fuse the two result sets directly."""
    seen: dict[str, Chunk] = {}
    with get_session() as session:
        for query in plan.sub_queries:
            rows = session.execute(
                """SELECT chunk_id, kb_id, doc_id, lower(block_span) AS lo, upper(block_span) - 1 AS hi,
                          text, order_confidence, degraded
                   FROM chunk WHERE kb_id = :kb AND tsv @@ plainto_tsquery('english', :q)
                   ORDER BY ts_rank(tsv, plainto_tsquery('english', :q)) DESC LIMIT :k""",
                {"kb": kb_id, "q": query, "k": plan.k_per_query},
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
