-- Vector store for the Bedrock Knowledge Base "riverbend-d2-manuals" (Aurora PostgreSQL + pgvector).
-- Applied by setup.py on every deploy. The table is rebuilt each time: run a sync afterwards.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS bedrock_kb;
DROP TABLE IF EXISTS bedrock_kb.manual_chunks;

CREATE TABLE bedrock_kb.manual_chunks (
  id               uuid PRIMARY KEY,
  embedding        vector(1536),
  chunk_text       text,
  metadata         json,
  custom_metadata  jsonb
);

CREATE INDEX manual_chunks_embedding_idx ON bedrock_kb.manual_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX manual_chunks_text_idx ON bedrock_kb.manual_chunks USING gin (to_tsvector('simple', chunk_text));
CREATE INDEX manual_chunks_custom_metadata_idx ON bedrock_kb.manual_chunks USING gin (custom_metadata);

GRANT USAGE ON SCHEMA bedrock_kb TO bedrock_kb_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON bedrock_kb.manual_chunks TO bedrock_kb_user;
