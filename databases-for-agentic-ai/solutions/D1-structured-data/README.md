# Mission D1 solution: The agent sees nothing, or everything

```bash
patch -p1 < solutions/D1-structured-data/fix.patch
./scripts/deploy.sh D1                     # re-applies db/grants.sql, updates Lambda code and env
python3 missions/D1-structured-data/scenarios/probe_tools.py
```

## Fault 1: the Lambda is configured with the admin secret

| | |
|---|---|
| Symptom | Every tool returns an error about not being authorized for `secretsmanager:GetSecretValue` on the `rds!cluster-…` (RDS-managed admin) secret |
| Where | `aws_lambda_function.tools` env `DB_SECRET_ARN = local.db.admin_secret_arn` |
| Root cause | The Data API authenticates to PostgreSQL with the secret you pass, after checking that the **caller** may read it. The role, correctly, may only read the app secret |
| Fix | `DB_SECRET_ARN = local.db.app_secret_arn`. The tempting "fix" of granting the role the admin secret would give an LLM-driven tool superuser rights over the whole database |

## Fault 2: the app user has privileges on the wrong schema

| | |
|---|---|
| Symptom | `ERROR: permission denied for schema reporting` |
| Where | `db/grants.sql` grants `USAGE ON SCHEMA commerce` and no `SELECT` at all |
| Fix | Revoke `commerce`. Grant `USAGE ON SCHEMA reporting` + `SELECT ON reporting.order_summary, reporting.category_activity` |

Views are executed with the **view owner's** privileges on the base tables, so the agent identity can read exactly the curated columns, with no PII columns and no raw tables. `dbsql.py --as app` on `commerce.customers` now fails, which is what you want.

## Fault 3: `orders_for_customer` is open to SQL injection and unbounded

| | |
|---|---|
| Symptom | The probe's hostile `customer_id` `C00112' OR customer_id LIKE 'C0001%` returns **110** orders across 11 customers |
| Root cause | The SQL is built with an f-string, so model-supplied text becomes SQL. There's no `LIMIT` either |
| Fix | 1. **Validate** the format (`^C\d{5}$`) before querying. 2. **Bind** parameters (`:cid`) through the Data API. 3. **Bound** the result (`LIMIT :lim`, max 20). The `statement_timeout` on the role bounds the time |

Prompt injection makes this realistic. A customer only has to *ask* the agent to look up `"C00112' OR …"`, and the model will faithfully pass it as the argument.

## Debrief answers

1. Prompts aren't access control. A separate identity confines the damage of any model mistake or injection to what that
   identity may do. It also shows up separately in `pg_stat_activity` and audit logs, and can have its own timeouts and connection limits.
2. A stable, documented contract (columns, joins, filters) that you can change without breaking the agent. Sensitive columns are excluded
   by construction. Business logic (for example excluding `CANCELLED`) lives in one place.
3. Defence in depth. Validation rejects nonsense early with a clear error for the model. Parameters stop injection. Limits protect
   the database, the Data API's 1 MB response limit and the model's context window from huge results.
4. From the **authenticated session**: the JWT or app session that the runtime received (see the Agentic AI kit's M1). Never trust a
   model-chosen value. D5 fixes exactly this.
