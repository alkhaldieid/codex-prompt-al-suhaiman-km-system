-- Step 1: shrink embedding to 1536 dims (pgvector HNSW supports up to 2000),
-- add HNSW index per spec §6.3, add fields needed for autotag (§7.2) and
-- regulatory seed (§5.5 — practice_area was stored only in chunks before).

-- pgvector HNSW does not support 3072 dims; truncate to 1536 via
-- text-embedding-3-large's Matryoshka dimensions parameter (set elsewhere).
ALTER TABLE document_chunks
  ALTER COLUMN embedding TYPE vector(1536) USING NULL;

CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
  ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 200);

-- practice_area was already TEXT[] in 001; do not redeclare.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS auto_tag_confidence JSONB;
-- summary_ar was declared in the original DDL outline but absent from the
-- initial migration; add idempotently for §7.3 precedent summarization.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS summary_ar TEXT;
