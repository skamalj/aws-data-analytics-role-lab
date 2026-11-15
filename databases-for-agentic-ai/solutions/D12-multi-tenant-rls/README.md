# Mission D12 solution: Tenants see each other

```bash
patch -p1 < solutions/D12-multi-tenant-rls/fix.patch
./scripts/deploy.sh D12
python3 missions/D12-multi-tenant-rls/scenarios/check.py
```

Verified on PostgreSQL 16 with the same SQL. As table owner, one search returned documents of **6 different tenants**. After the fix, one tenant only, 10 rows.

## Fault 1: the service identity owns the table, so RLS doesn't apply to it

| | |
|---|---|
| Root cause | PostgreSQL doesn't apply row-level security to the **table owner** (or superusers, or roles with `BYPASSRLS`) unless the table has `FORCE ROW LEVEL SECURITY`. `ALTER TABLE … OWNER TO saas_app` made every policy irrelevant for the service |
| Fix | Keep ownership with the admin and `GRANT SELECT` to `saas_app`, plus `ALTER TABLE … FORCE ROW LEVEL SECURITY` as defence in depth. Run migrations as a separate deployer identity |

## Fault 2: the tenant is set in a different "session" from the query

| | |
|---|---|
| Symptom | After fix 1: 0 results, or occasionally another tenant's results |
| Root cause | `set_config('app.tenant_id', :t, false)` and the `SELECT` were two independent Data API calls. They can land on different pooled connections (the query then sees no tenant → 0 rows), and a non-local setting can survive on a connection and be picked up by an unrelated request |
| Fix | One Data API **transaction**: `begin_transaction` → `set_config(…, true)` (transaction-local) → query → commit. When the transaction ends, so does the setting |

## Fault 3: filtered HNSW search returns too few rows

| | |
|---|---|
| Root cause | The index scan yields at most `ef_search` (default 40) nearest candidates *before* RLS filters them. With ~5 % of rows per tenant, ~2–6 survive |
| Fix | `ALTER ROLE saas_app SET hnsw.ef_search = 400`. On pgvector ≥ 0.8 (Aurora PostgreSQL 16.6+), prefer `SET hnsw.iterative_scan = relaxed_order`, which keeps scanning until LIMIT rows pass the filter. For very large tenants, partial indexes or partitioning by tenant avoid the problem altogether |

## Debrief answers

1. Fail closed. `current_setting(name, true)` returns NULL when unset, and `tenant_id = NULL` is never true, so a forgotten setting returns nothing
   instead of everything.
2. Table- or schema-per-tenant: strong isolation and per-tenant indexes (good recall), but many objects to manage and migrate. RLS on one table: simple
   operations and one index, but you depend on the policy being correct and filtered ANN search needs tuning. Large or VIP tenants can be split out.
3. With iterative scans the index keeps producing candidates until enough rows pass the filter (bounded by `hnsw.max_scan_tuples`), so `ef_search` goes back
   to being a recall knob rather than a row cap.
4. That it comes from the **authenticated identity** (JWT claim, API key mapping), never from request bodies or model output. The agent can't choose
   its tenant.
