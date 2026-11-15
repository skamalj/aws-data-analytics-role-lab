-- Two candidate vector indexes for Trail Desk's "similar reviews" feature, 20,000 review embeddings each
-- (128-d, synthetic: ~250 topic clusters). The tables are rebuilt on every deploy.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS vectors;
DROP TABLE IF EXISTS vectors.reviews_ivf;
DROP TABLE IF EXISTS vectors.reviews_hnsw;
CREATE TABLE vectors.reviews_ivf  (id int PRIMARY KEY, embedding vector(128) NOT NULL);
CREATE TABLE vectors.reviews_hnsw (id int PRIMARY KEY, embedding vector(128) NOT NULL);

-- IVFFlat: inverted lists over k-means centroids
CREATE INDEX reviews_ivf_idx ON vectors.reviews_ivf USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1000);

INSERT INTO vectors.reviews_ivf
SELECT g, (SELECT array_agg(sin((g % 250) * 1.37 + d * 0.91) * cos((g % 250) * 0.11 * d) + (random() - 0.5) * 0.6)::vector
           FROM generate_series(1, 128) AS d WHERE g > 0)       -- ~250 topics, each review = topic + noise
FROM generate_series(1, 20000) g;
INSERT INTO vectors.reviews_hnsw SELECT id, embedding FROM vectors.reviews_ivf;

-- HNSW: proximity graph
CREATE INDEX reviews_hnsw_idx ON vectors.reviews_hnsw USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
ANALYZE vectors.reviews_ivf;
ANALYZE vectors.reviews_hnsw;

GRANT USAGE ON SCHEMA vectors TO trail_desk_app;
GRANT SELECT ON vectors.reviews_ivf, vectors.reviews_hnsw TO trail_desk_app;

-- Search settings for the application identity
ALTER ROLE trail_desk_app SET ivfflat.probes = 1;
ALTER ROLE trail_desk_app RESET hnsw.ef_search;
