# Mission D1: The agent sees nothing, or everything

**Skills:** least-privilege database identities, curated views, Secrets Manager credentials with the RDS Data API, Gateway Lambda tools over SQL, SQL injection through model-supplied arguments, bounded results
**Time:** 40–50 minutes  |  **Needs:** `./scripts/deploy.sh base` (once), then `./scripts/deploy.sh D1`

## Situation

Trail Desk answers order questions with three **SQL tools**. They're one Lambda function behind
an AgentCore Gateway, reading the shared Aurora PostgreSQL cluster through the **RDS Data API**:

| Tool | Reads |
|---|---|
| `get_order(order_id)` | `reporting.order_summary` |
| `orders_for_customer(customer_id)` | `reporting.order_summary` |
| `category_activity(category)` | `reporting.category_activity` |

Riverbend's data policy:
- The agent uses the database identity **`trail_desk_app`** (credentials in the `riverbend-db-app-*` secret). It **never** uses the admin user.
- That identity may read the **curated `reporting` views only**. Raw `commerce` tables hold customer PII and are off-limits.
- Tools must be safe against whatever text the model passes them, because that text ultimately comes from customers.

```
Trail Desk ──MCP──► Gateway ──► Lambda riverbend-d1-order-tools ──Data API (secret)──► Aurora: reporting.* views ─► commerce.* tables
```

Your files: [`terraform/main.tf`](terraform/main.tf), [`lambdas/order_tools.py`](lambdas/order_tools.py),
[`db/grants.sql`](db/grants.sql) (applied by `setup.py` on every deploy).

## Symptoms

```bash
python3 common/chat.py D1 "Where is order O1003?"
python3 missions/D1-structured-data/scenarios/probe_tools.py     # calls the Lambda exactly like the gateway does
```

Nothing works yet. Fix the first error and the next one appears. Then pay attention to the probe's
**last** check: something works that shouldn't.

## Objectives

1. All three tools work for normal input, using `trail_desk_app` only.
2. `trail_desk_app` can read the two `reporting` views and **nothing in `commerce`**.
3. A hostile `customer_id` can't return other customers' orders, and no tool returns an unbounded number of rows.
4. Don't fix anything by giving the Lambda the admin secret or by granting `commerce` access.

## Done when

```
PASS  get_order works
PASS  category_activity works
PASS  orders_for_customer works
PASS  hostile input returns no other customers' orders
```

and:

```bash
python3 common/chat.py D1 "Where is order O1003?"          # SHIPPED, 2026-02-09, web, 238.00, Trail Runner
python3 common/chat.py D1 "How are tents selling?"          # 1612 order lines, 3252 units, latest 2026-10-27
python3 common/dbsql.py --as app --sql "SELECT count(*) FROM commerce.customers"   # must FAIL (permission denied)
```

## Investigation toolkit

```bash
aws logs tail /aws/lambda/riverbend-d1-order-tools --since 10m
aws lambda get-function-configuration --function-name riverbend-d1-order-tools --query Environment
terraform -chdir=base/terraform output                                    # which secret is which
python3 common/dbsql.py --sql "SELECT grantee, table_schema, table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee='trail_desk_app'"
python3 common/dbsql.py --sql "SELECT nspname, has_schema_privilege('trail_desk_app', nspname, 'USAGE') FROM pg_namespace WHERE nspname IN ('commerce','reporting')"
python3 common/dbsql.py --as app --sql "SELECT current_user"
```

## Hint ladder

<details><summary>Hint 1: who is the Lambda, in the database?</summary>

The Data API logs in with whatever secret you pass it, and the *caller* (the Lambda role) must be allowed to read that secret. Which secret does the Lambda use, and which one may its role read? Fix the **choice of secret**, not the IAM policy.
</details>

<details><summary>Hint 2: schema vs object privileges</summary>

PostgreSQL needs `USAGE` on a schema **and** `SELECT` on the object. Which schema holds the views the tools read? A view runs with its *owner's* rights on the underlying tables, so the app user needs nothing on `commerce`.
</details>

<details><summary>Hint 3: the last probe</summary>

Look at how `orders_for_customer` builds its SQL, compared with the other two tools. The Data API supports named parameters (`:name`).
</details>

## Red herrings

- The gateway, the agent's permissions and the tool schemas are fine.
- `statement_timeout = 5s` on `trail_desk_app` is intentional.
- The cluster may be auto-paused. The first query can take about 30 s, and `dbsql.py` waits for it.

## Debrief questions

1. Why is a separate database identity for the agent better than "the app's admin user, but with a careful prompt"?
2. What do curated views give you that table grants alone don't?
3. Parameterising stops injection. Why validate the format **and** cap the rows as well?
4. The model chose `customer_id`. In production, where should that value come from? (Mission D5 comes back to this.)
