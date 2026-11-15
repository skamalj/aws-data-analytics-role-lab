-- Multi-tenant document store: one table, row-level security on tenant_id (applied by post_deploy.py).
-- 20 tenants x 1,500 documents, 64-d embeddings (synthetic: ~40 topics per tenant).
CREATE EXTENSION IF NOT EXISTS vector;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'saas_app') THEN CREATE ROLE saas_app LOGIN; END IF;
END $$;
ALTER ROLE saas_app PASSWORD '{{SAAS_PASSWORD}}';
GRANT CONNECT ON DATABASE riverbend TO saas_app;
GRANT saas_app TO CURRENT_USER;

CREATE SCHEMA IF NOT EXISTS saas;
GRANT USAGE ON SCHEMA saas TO saas_app;
DROP TABLE IF EXISTS saas.tenant_docs;
CREATE TABLE saas.tenant_docs (
  id         bigint PRIMARY KEY,
  tenant_id  text NOT NULL,
  title      text NOT NULL,
  embedding  vector(64) NOT NULL
);
INSERT INTO saas.tenant_docs
SELECT g, 'tenant-' || lpad((g % 20)::text, 2, '0'), 'Document ' || g,
       (SELECT array_agg(sin((g % 800) * 1.37 + d * 0.91) + (random() - 0.5) * 0.4)::vector
          FROM generate_series(1, 64) AS d WHERE g > 0)
FROM generate_series(1, 30000) g;
CREATE INDEX tenant_docs_embedding_idx ON saas.tenant_docs USING hnsw (embedding vector_cosine_ops);
ANALYZE saas.tenant_docs;

-- Tenant isolation: a session only sees rows of the tenant in app.tenant_id
ALTER TABLE saas.tenant_docs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON saas.tenant_docs
  USING (tenant_id = current_setting('app.tenant_id', true));

-- The SaaS service owns its table so its migrations can run without the DBA
ALTER TABLE saas.tenant_docs OWNER TO saas_app;
