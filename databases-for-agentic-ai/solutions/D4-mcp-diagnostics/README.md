# Mission D4 solution: The debug tool is a backdoor

```bash
patch -p1 < solutions/D4-mcp-diagnostics/fix.patch
./scripts/deploy.sh D4
python3 missions/D4-mcp-diagnostics/scenarios/audit.py
```

## Fault 1: the advertised schema doesn't match the handler

| | |
|---|---|
| Symptom | `describe_table` called as advertised (`{"table": "commerce.orders"}`) returns `KeyError: 'table_name'` |
| Fix | Advertise `table_name`, the same name the handler and the other tools use. Keep schema and handler in one place, and test tools through `tools/list` the way the audit does |

## Fault 2: a write path, through all three layers

| Layer | Broken | Fixed |
|---|---|---|
| Tools | `run_sql` runs **any** statement | Removed. Diagnostics get purpose-built, read-only tools |
| Database identity | `DB_SECRET_ARN` = **admin** secret (superuser-like `dbadmin`) | `diag_readonly`: `SELECT` only on the three schemas, `default_transaction_read_only = on`, `statement_timeout = 5s` |
| IAM | `secretsmanager:GetSecretValue` on the admin secret, `dynamodb:*` on `*` | Only the diag secret. `dynamodb:DescribeTable` + `Scan` on the one sessions table |

Any one layer alone would have stopped the canary `UPDATE`. Least privilege means each layer is correct on its own, so a future bug in one of them, like someone re-adding `run_sql`, still can't write.

## Fault 3: unbounded, unredacted samples

| | |
|---|---|
| Symptom | `sample_rows commerce.customers limit 100000` returns all 500 customers with e-mails and phones. `ddb_sample` returns every item, with e-mails |
| Fix | `cap()`: limit between 1 and 20 (default 5). `redact()`: mask columns named like `email`/`phone`/`full_name`/`address`, and any e-mail-shaped value. `ddb_*` tools accept only the configured tables |

Diagnostics should show *shape* (types, nulls, example formats), not harvest data. Sampled PII ends up in coding-agent transcripts, terminals and tickets.

## Debrief answers

1. Agents act autonomously and can be steered by injected content, such as a malicious row or a README. Whatever the server *can* do,
   an agent can be talked into doing. Authorization has to be in the server and its identities, not in who you expect to use it.
2. All of them. Removing the tool shrinks the attack surface. The DB role is the authoritative control at the data. IAM limits which
   credentials can even be read. `default_transaction_read_only` is a guard rail, because a session can turn it off. Defence in depth.
3. A separate server or workflow with a different identity, stronger auth (human approval, change tickets), and auditing.
   Never a "mode" flag in the read-only server.
4. If the agent itself may only read `reporting` views, then diagnostics shouldn't give its operators unredacted customer tables.
   Expose metadata and redacted samples, and send real data access through the normal, audited data-access process.
