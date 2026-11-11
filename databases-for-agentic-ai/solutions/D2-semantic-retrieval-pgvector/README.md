# Mission D2 solution: Manuals in, nothing out

```bash
patch -p1 < solutions/D2-semantic-retrieval-pgvector/fix.patch
./scripts/deploy.sh D2                 # setup.py rebuilds the table, then terraform updates the KB role / creates the KB
$(terraform -chdir=missions/D2-semantic-retrieval-pgvector/terraform output -raw sync_command)
```

## Fault 1: the KB role can't read the database secret

| | |
|---|---|
| Symptom | `CreateKnowledgeBase` fails with an error about not being able to access or get the secret `riverbend-db-kb-*` |
| Where | KB role policy: Data API and DescribeDBClusters, but no `secretsmanager:GetSecretValue` |
| Root cause | Bedrock connects through the RDS Data API **using the KB role**. The Data API in turn requires the caller to read the secret it should log in with |
| Fix | `secretsmanager:GetSecretValue` on `kb_secret_arn` only, not on the admin or app secrets |

## Fault 2: `field_mapping.text_field` names a column that doesn't exist

| | |
|---|---|
| Symptom | The KB is rejected (or ingestion fails) because column `chunks` isn't found |
| Where | `kb_schema.sql` calls it `chunk_text`. Terraform maps `text_field = "chunks"` |
| Fix | Rename the column to `chunks` (and its GIN full-text index). Changing the mapping instead would also work, but `chunks` is the convention AWS documentation and tooling use |

## Fault 3: the vector column has the wrong dimensions

| | |
|---|---|
| Symptom | `vector(1536)` vs the model's 1024-dimension embeddings. Depending on where it's caught: KB validation or ingestion reports a dimension mismatch, and every chunk fails (`numberOfDocumentsFailed: 5`) |
| Root cause | A pgvector column `vector(N)` only accepts vectors of exactly N dimensions. 1536 is the dimension of older embedding models (Titan V1 and others), probably copied from another project |
| Fix | `embedding vector(1024)`. `setup.py` drops and recreates the table, so re-run the **sync** |

## Final table

```sql
CREATE TABLE bedrock_kb.manual_chunks (
  id uuid PRIMARY KEY, embedding vector(1024), chunks text, metadata json, custom_metadata jsonb);
CREATE INDEX ON bedrock_kb.manual_chunks USING hnsw (embedding vector_cosine_ops);          -- similarity search
CREATE INDEX ON bedrock_kb.manual_chunks USING gin (to_tsvector('simple', chunks));        -- hybrid / keyword search
CREATE INDEX ON bedrock_kb.manual_chunks USING gin (custom_metadata);                      -- metadata filters
GRANT USAGE ON SCHEMA bedrock_kb TO bedrock_kb_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON bedrock_kb.manual_chunks TO bedrock_kb_user;
```

## Debrief answers

1. **HNSW** on `embedding` with the operator class that matches the distance (here cosine) for approximate nearest-neighbour search.
   **GIN on `to_tsvector(chunks)`** for the keyword half of hybrid search. **GIN on `custom_metadata`** for metadata filtering.
2. The column type (`vector(512)`), the HNSW index and the KB's embedding configuration must all change, and every document must be
   re-embedded (re-sync). Vectors from different models can't be compared, even when the dimensions match.
3. Pros: one database to secure, back up and monitor. You can join chunks with relational data in SQL, and there's no extra service.
   Cons: vector workloads compete with OLTP for capacity and connections, scaling is tied to the cluster, and HNSW builds use memory.
   Dedicated stores scale independently and S3 Vectors is far cheaper at large scale.
4. Tag documents with metadata (a `.metadata.json` file next to each object, for example `{"audience": "staff"}`), and **filter in
   `Retrieve`** based on the authenticated caller's role (`vectorSearchConfiguration.filter`). The application builds that filter, not the model.
