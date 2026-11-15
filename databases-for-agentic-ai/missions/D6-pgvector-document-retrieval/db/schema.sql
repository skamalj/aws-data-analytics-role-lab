-- Document store for Trail Desk's own pgvector retrieval (no Knowledge Base). Re-runnable.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE IF NOT EXISTS knowledge.doc_chunks (
  id         bigserial PRIMARY KEY,
  doc        text NOT NULL,
  chunk_no   int  NOT NULL,
  content    text NOT NULL,
  embedding  vector(1024) NOT NULL,
  UNIQUE (doc, chunk_no)
);

-- Approximate nearest-neighbour index for the search_docs tool
DROP INDEX IF EXISTS knowledge.doc_chunks_embedding_idx;
CREATE INDEX doc_chunks_embedding_idx ON knowledge.doc_chunks USING hnsw (embedding vector_l2_ops);

-- The agent's tools log in as trail_desk_app
GRANT USAGE ON SCHEMA knowledge TO trail_desk_app;
