-- Chunk store written by the D9 ingestion Lambda (as bedrock_kb_user). Re-runnable.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE TABLE IF NOT EXISTS knowledge.d9_chunks (
  id           bigserial PRIMARY KEY,
  doc_key      text NOT NULL,
  chunk_no     int  NOT NULL,
  content      text NOT NULL,
  embedding    vector(1024) NOT NULL,
  source_uri   text NOT NULL,
  ingested_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS d9_chunks_embedding_idx ON knowledge.d9_chunks USING hnsw (embedding vector_cosine_ops);
GRANT USAGE ON SCHEMA knowledge TO bedrock_kb_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge.d9_chunks TO bedrock_kb_user;
GRANT USAGE, SELECT ON SEQUENCE knowledge.d9_chunks_id_seq TO bedrock_kb_user;
