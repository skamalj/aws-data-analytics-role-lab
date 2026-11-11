# Mission D4: The debug tool is a backdoor

**Skills:** Model Context Protocol servers on AgentCore Runtime (`server_protocol = "MCP"`), tool schemas vs handlers, read-only diagnostic identities (PostgreSQL + IAM), result limits and redaction, separating diagnostics from administration
**Time:** 40–50 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D4`

## Situation

To help engineers debug Trail Desk's data layer, a developer built an **MCP server**
([`mcp/server.py`](mcp/server.py)) and deployed it to AgentCore Runtime. Engineers connect it to
their coding agents, which then call tools like `describe_table` and `sample_rows` by themselves.

Before anyone outside the team can use it, security runs a review.
[`scenarios/audit.py`](scenarios/audit.py) is that review, and it fails badly.

```
engineer's coding agent ──MCP (SigV4)──► AgentCore Runtime riverbend_d4_db_diagnostics (POST /mcp)
                                            ├─ Data API (DB_SECRET_ARN) ──► Aurora: commerce, reporting, bedrock_kb
                                            └─ DynamoDB ──► riverbend-d4-web-sessions
```

The platform team already created a read-only database identity for exactly this,
`diag_readonly` (`riverbend-db-diag-*` secret, grants in [`db/diag_grants.sql`](db/diag_grants.sql)).

## Symptoms

```bash
python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py tools
python3 missions/D4-mcp-diagnostics/scenarios/audit.py
```

## Objectives

1. Every tool works when called **exactly as advertised** in `tools/list`.
2. No tool can change data, in PostgreSQL or DynamoDB.
3. The server uses the read-only database identity, and its IAM role can do no more than the tools need.
4. Samples return at most **20** rows or items, and personal data (e-mail, phone, names) is redacted.
5. Diagnostics stay useful: listing, describing and sampling must still work.

## Done when

```
PASS  server lists its tools
PASS  describe_table works
PASS  sample_rows is capped (<= 20 rows)
PASS  sample_rows redacts personal data
PASS  ddb_sample is capped and redacted
PASS  no tool can modify data
PASS  server uses the read-only database identity
PASS  role cannot write DynamoDB or read the admin secret

8/8 checks passed
```

## Investigation toolkit

```bash
python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py tools
python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py call describe_table '{"table": "commerce.orders"}'
python3 missions/D4-mcp-diagnostics/scenarios/mcp_client.py call sample_rows '{"table_name": "commerce.customers", "limit": 3}'
aws logs tail "$(terraform -chdir=missions/D4-mcp-diagnostics/terraform output -raw log_group_hint)" --since 10m
aws iam get-role-policy --role-name <runtime role> --policy-name diagnostics-access
python3 common/dbsql.py --as diag --sql "UPDATE commerce.audit_canary SET note = note WHERE id = 1"   # should fail
```

## Hint ladder

<details><summary>Hint 1: describe_table</summary>

An MCP client only knows what `tools/list` says. Compare the advertised `inputSchema` with the key the handler reads.
</details>

<details><summary>Hint 2: least privilege, three layers</summary>

Which tool can write? Which database user does the server log in as? What can its IAM role do in DynamoDB and Secrets Manager? Read-only must hold at **every** layer, not only in the code.
</details>

<details><summary>Hint 3: what a sample may return</summary>

What happens with `limit: 100000`? Which columns of `commerce.customers` and which DynamoDB attributes are personal data?
</details>

## Red herrings

- The MCP transport (stateless streamable HTTP on `:8000/mcp`) works.
- `IDENT` (schema.table validation) does its job against SQL injection through table names.
- The cluster may be auto-paused. The first call can take ~30 s.

## Debrief questions

1. Why is "the tool is only for engineers" not a security argument once it's an MCP server that agents call by themselves?
2. Which layer enforces "read-only" best: removing the tool, the database role, `default_transaction_read_only`, or IAM? Why use all of them?
3. How would you offer *administrative* actions (for example, re-running a migration) without mixing them into this server?
4. Diagnostics access should be "no broader than the agent's real permissions". What does that mean for `commerce.customers`?
