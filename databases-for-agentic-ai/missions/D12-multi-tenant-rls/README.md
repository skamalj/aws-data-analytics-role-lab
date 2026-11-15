# Mission D12: Tenants see each other

**Based on:** *Self-managed multi-tenant vector search with Amazon Aurora PostgreSQL* (AWS Database Blog): one table with a `tenant_id` column, HNSW, and PostgreSQL row-level security (RLS)
**Skills:** RLS policies driven by session settings, who bypasses RLS (owners, `BYPASSRLS`), `FORCE ROW LEVEL SECURITY`, session state with the RDS Data API (transactions, `set_config(…, true)`), filtered HNSW search (`ef_search`, iterative scans)
**Time:** 45 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D12`

## Situation

Riverbend now resells Trail Desk to **20 partner shops** (tenants). Their documents live in one table,
`saas.tenant_docs`, isolated by a row-level security policy:

```sql
CREATE POLICY tenant_isolation ON saas.tenant_docs USING (tenant_id = current_setting('app.tenant_id', true));
```

The document service ([`lambdas/tenant_search.py`](lambdas/tenant_search.py)) logs in as its own identity, `saas_app`.
For every request it sets `app.tenant_id` to the **authenticated** tenant, then runs a "more like this" vector search.
The schema and policy are in [`db/tenancy.sql`](db/tenancy.sql), applied by `post_deploy.py`.

## Symptoms

```bash
python3 missions/D12-multi-tenant-rls/scenarios/check.py
aws lambda invoke --function-name riverbend-d12-tenant-search --payload '{"tenant_id":"tenant-01","doc_id":21}' \
  --cli-binary-format raw-in-base64-out /dev/stdout
```

A partner has reported seeing *other partners'* documents. Fix that, and the results go empty or come back short.

## Objectives

1. A tenant only ever sees its own documents, whatever the code or identity does.
2. Every search returns the full top 10 of the caller's tenant.
3. Isolation must hold even if a future developer forgets to set the tenant, so failure must mean "no rows", never "all rows".
4. Keep the single-table design, the HNSW index and the `saas_app` identity.

## Done when

`check.py` reports 4/4 checks passed.

## Investigation toolkit

```bash
python3 common/dbsql.py --sql "SELECT tableowner, relrowsecurity, relforcerowsecurity FROM pg_tables JOIN pg_class ON relname = tablename WHERE tablename = 'tenant_docs'"
python3 common/dbsql.py --sql "SELECT polname, pg_get_expr(polqual, polrelid) FROM pg_policy WHERE polrelid = 'saas.tenant_docs'::regclass"
python3 common/dbsql.py --sql "SELECT tenant_id, count(*) FROM saas.tenant_docs GROUP BY 1 ORDER BY 1 LIMIT 3"
aws logs tail /aws/lambda/riverbend-d12-tenant-search --since 10m
```

## Hint ladder

<details><summary>Hint 1: everybody sees everything</summary>RLS is enabled and the policy looks right. Which roles does PostgreSQL <b>not</b> apply policies to? Who owns the table?</details>
<details><summary>Hint 2: then nobody sees anything</summary>Each Data API <code>execute_statement</code> may run on a different pooled connection. Where does the <code>set_config</code> end up, and is it still there for the query? (A setting left on a pooled connection could even be seen by the <i>next</i> tenant's request.)</details>
<details><summary>Hint 3: 6 rows instead of 10</summary>The HNSW scan produces up to <code>hnsw.ef_search</code> candidates, and RLS filters them <i>afterwards</i>. Each tenant owns ~5 % of the rows.</details>

## Debrief questions

1. Why should a missing tenant setting return zero rows, and how does `current_setting('app.tenant_id', true)` give you that?
2. Compare table-per-tenant, schema-per-tenant and RLS for vector search.
3. How do iterative index scans (pgvector 0.8) change the `ef_search` trade-off?
4. What must the API layer guarantee about `tenant_id`?
