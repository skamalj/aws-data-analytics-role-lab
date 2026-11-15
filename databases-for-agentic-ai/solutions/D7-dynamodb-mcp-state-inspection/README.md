# Mission D7 solution: The memory inspector shows an empty brain

```bash
patch -p1 < solutions/D7-dynamodb-mcp-state-inspection/fix.patch
./scripts/deploy.sh D7
aws dynamodb delete-table --table-name riverbend-d7-checkpoint     # the stray table the broken inspector created
python3 missions/D7-dynamodb-mcp-state-inspection/scenarios/audit.py
```

## Fault 1: wrong table name, and a role that can create tables

| | |
|---|---|
| Symptom | `describe_memory_table`/`list_threads` fail with `ResourceNotFoundException`. After any `get_conversation` call they return **nothing**, and a new table `riverbend-d7-checkpoint` (singular) appears in the account |
| Root cause | The runtime env `CHECKPOINT_TABLE = "riverbend-d7-checkpoint"` doesn't match the real table, `riverbend-d7-checkpoints`. `DynamoDBSaver`, constructed on the first `get_conversation`, runs `table.load()`. On `ResourceNotFoundException` it **creates** the table. The role's `dynamodb:*` on `riverbend-d7-*` allowed that, so the typo turned into a new, empty table instead of an error |
| Fix | `CHECKPOINT_TABLE = aws_dynamodb_table.memory.name` (a reference, not a typed string), plus a role that can't create tables, so any future mismatch fails loudly. Delete the stray table |

## Fault 2: the inspector can change memory

| | |
|---|---|
| Where | Tool `delete_thread` (calls `saver.delete_thread`) and IAM `dynamodb:*` |
| Fix | Remove the tool. IAM: `DescribeTable`, `DescribeTimeToLive`, `GetItem`, `Query`, `Scan` on **the one table ARN**. `DescribeTable` is needed because the saver checks the table on start-up |

## Fault 3: unbounded, unredacted state

| | |
|---|---|
| Symptom | `get_conversation sizing-C00042-s1` returns 50 messages and ~120 KB. `support-C00112-c1` shows `dana.k@example.com` and `+1-555-0177` |
| Fix | `last_n` (default 10, max 20). Truncate each message to 500 characters. Redact e-mail and phone patterns |

## Debrief answers

1. The item layout (`PK`/`SK`, the serialised `type` + `checkpoint` blob, pending writes) is an implementation detail of the library. Using
   the saver's `get_tuple()`/`list()` decodes it exactly as the agent wrote it, and keeps working when the format changes in a new version.
2. Without `CreateTable`, the saver's "create if missing" path fails with AccessDenied. A wrong name surfaces at once, instead of silently creating
   an empty table that makes every query "succeed" with no data.
3. `DescribeTable` (the saver's start-up check), `DescribeTimeToLive` (the describe tool), `GetItem` (consistent reads in `get_tuple`), `Query`, and `Scan`
   (thread listing only).
4. In an audited, authorised workflow, for example a Step Functions job triggered by the privacy team. It runs under its own role with
   `DeleteItem`/`BatchWriteItem` and calls `saver.delete_thread()` for every thread of the customer. It doesn't belong in a debugging tool.
