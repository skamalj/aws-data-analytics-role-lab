-- Vector store for the multi-tenant knowledge base riverbend-d13-partners. Re-runnable.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS bedrock_kb.d13_chunks (
  id uuid PRIMARY KEY, embedding vector(1024), chunks text, metadata json, custom_metadata jsonb);
CREATE INDEX IF NOT EXISTS d13_chunks_embedding_idx ON bedrock_kb.d13_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS d13_chunks_text_idx ON bedrock_kb.d13_chunks USING gin (to_tsvector('simple', chunks));
CREATE INDEX IF NOT EXISTS d13_chunks_custom_metadata_idx ON bedrock_kb.d13_chunks USING gin (custom_metadata);
GRANT USAGE ON SCHEMA bedrock_kb TO bedrock_kb_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON bedrock_kb.d13_chunks TO bedrock_kb_user;
