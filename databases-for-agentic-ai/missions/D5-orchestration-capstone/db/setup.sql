-- D5 starts from the corrected D1/D2 database design (applied by setup.py on every deploy).
REVOKE ALL ON ALL TABLES IN SCHEMA commerce FROM trail_desk_app;
REVOKE USAGE ON SCHEMA commerce FROM trail_desk_app;
GRANT USAGE ON SCHEMA reporting TO trail_desk_app;
GRANT SELECT ON reporting.order_summary, reporting.category_activity TO trail_desk_app;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS bedrock_kb.d5_chunks (
  id uuid PRIMARY KEY, embedding vector(1024), chunks text, metadata json, custom_metadata jsonb);
CREATE INDEX IF NOT EXISTS d5_chunks_embedding_idx ON bedrock_kb.d5_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS d5_chunks_text_idx ON bedrock_kb.d5_chunks USING gin (to_tsvector('simple', chunks));
CREATE INDEX IF NOT EXISTS d5_chunks_custom_metadata_idx ON bedrock_kb.d5_chunks USING gin (custom_metadata);
GRANT USAGE ON SCHEMA bedrock_kb TO bedrock_kb_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON bedrock_kb.d5_chunks TO bedrock_kb_user;
