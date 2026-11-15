-- Passage store for the fast-answer tool. Rebuilt on every deploy; post_deploy.py re-embeds the
-- documents at whatever dimension this column declares.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS knowledge;
DROP TABLE IF EXISTS knowledge.d11_chunks;
CREATE TABLE knowledge.d11_chunks (
  id        bigserial PRIMARY KEY,
  doc       text NOT NULL,
  chunk_no  int  NOT NULL,
  content   text NOT NULL,
  embedding vector(1024) NOT NULL
);
CREATE INDEX d11_chunks_embedding_idx ON knowledge.d11_chunks USING hnsw (embedding vector_cosine_ops);
GRANT USAGE ON SCHEMA knowledge TO trail_desk_app;
GRANT SELECT ON knowledge.d11_chunks TO trail_desk_app;
