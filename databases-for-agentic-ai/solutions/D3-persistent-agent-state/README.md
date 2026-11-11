# Mission D3 solution: Resume fails, and then the state explodes

```bash
patch -p1 < solutions/D3-persistent-agent-state/fix.patch
./scripts/deploy.sh D3        # the table is REPLACED (new key schema), so old checkpoints are discarded
python3 missions/D3-persistent-agent-state/scenarios/resume.py
python3 missions/D3-persistent-agent-state/scenarios/long_chat.py
python3 missions/D3-persistent-agent-state/scenarios/check_ttl.py
```

## Fault 1: the role can't describe the table

| | |
|---|---|
| Symptom | First request: `AccessDeniedException … dynamodb:DescribeTable` |
| Root cause | `DynamoDBSaver.__init__` calls `_get_or_create_table()`, which runs `table.load()` (**DescribeTable**). On `ResourceNotFoundException` it would create the table. Any other error, including AccessDenied, is raised. The role only had item-level actions |
| Fix | Add `dynamodb:DescribeTable` on the table ARN. **Don't** add `CreateTable`: the table is created by Terraform, so the saver's "create if missing" branch is never needed, and an agent role that can create tables is a liability |

## Fault 2: the table's key schema isn't the saver's

| | |
|---|---|
| Symptom | `ValidationException: Query condition missed key schema element: thread_id`. Writes would fail the same way |
| Root cause | The saver uses a single-table design with **`PK` (S) and `SK` (S)**. Checkpoints are stored as `PK = <thread_id>`, `SK = <checkpoint_id>`, and pending writes get their own `SK`. Terraform created `thread_id` / `checkpoint_id` keys |
| Fix | `hash_key = "PK"`, `range_key = "SK"`. Key schemas can't be changed in place, so Terraform replaces the table |

## Fault 3: state is keyed on the runtime session

| | |
|---|---|
| Symptom | `resume.py` FAIL. Visit 2 shows `thread_id: riverbend-<uuid>` (a different value) and only 2 messages. The agent asks "which order?" |
| Root cause | `app.py` used the AgentCore **runtime session id** as `thread_id`. Runtime sessions are compute sessions that end after idle time. The customer's conversation outlives them |
| Fix | `thread_id = f"returns-{payload['conversation_id']}"`, the web app's stable conversation id, and reject requests without one. Prefixing the workflow type keeps different graphs for one conversation apart |

## Fault 4: checkpoints never expire

| | |
|---|---|
| Symptom | `check_ttl.py`: TTL enabled on `expires_at`, `0/N items have a numeric 'expires_at'` |
| Root cause | Two halves of one mistake. The saver writes **`ttl`** (epoch seconds) only when `ttl_seconds` is passed. The saver enables TTL only on tables **it creates**. With a Terraform-owned table, Terraform must set `attribute_name = "ttl"` |
| Fix | `ttl { attribute_name = "ttl" }` + `DynamoDBSaver(..., ttl_seconds=int(os.environ["CHECKPOINT_TTL_SECONDS"]))` with 604800 (7 days) |

Expiry is a background process, so items can stay visible for some time after `ttl` passes. Code that must not see stale state should filter on `ttl` itself.

## Fault 5: unbounded message history hits the 400 KB item limit

| | |
|---|---|
| Symptom | `long_chat.py` fails around turn 8–10: `ValidationException … PutItem: Item size has exceeded the maximum allowed size`. The runtime log also has the saver's start-up hint: *"DynamoDBSaver was built without reducer=, so message history grows without bound…"* |
| Root cause | A LangGraph checkpoint contains the full `messages` channel. Every 30 KB tool result stays in it, and every new checkpoint item is bigger than the last, until it exceeds DynamoDB's **400 KB** item limit |
| Fix | `reducer=MessageReducer(config=ReducerConfig(max_messages=20, min_messages=10))` from `agentstate-reducer` (installed by the `[reducer]` extra). The saver prunes the history **before** each `put()`. It keeps whole messages, keeps tool-call/tool-result pairs together, and keeps the first message |

Alternatives, and why they're weaker: putting big tool results in S3 and storing a pointer reduces the size but still grows without limit. Raising nothing isn't possible either, because 400 KB is a hard DynamoDB limit. Token-budget mode (`ReducerConfig(max_tokens=…)`) is a good refinement when message sizes vary a lot.

## Final least-privilege policy

```hcl
actions = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem",
           "dynamodb:Query", "dynamodb:BatchWriteItem", "dynamodb:DeleteItem"]
resources = [aws_dynamodb_table.checkpoints.arn]
```

- `BatchWriteItem` and `DeleteItem` are for `delete(thread)` and pruning.
- Add `dynamodb:Scan` only if you use `delete_for_runs()` without a GSI.

## Debrief answers

1. The session id identifies a compute session. The conversation id identifies the work. Use `customer_id + conversation_id`
   (or check ownership) when conversation ids could be guessed, so one customer can't resume another's thread.
2. Channel values (here the message list), channel versions, metadata (step, source, run id), pending writes and a parent
   pointer. Each super-step writes a new checkpoint holding the current full state, so state that only grows means items that only grow.
3. Use `ReducerConfig(on_prune=[...])`. Pruned turns are handed to hooks together with the run's `memory_namespace`
   (for example `("memories", customer_id)`). Point it at a long-term memory engine such as `langgraph-memory`, so facts survive pruning.
4. Expired items may still be read until DynamoDB deletes them, typically within days. Filter on `ttl > now` if that matters,
   and don't use TTL for anything that must happen on time.
5. DescribeTable, GetItem, PutItem, Query, BatchWriteItem, DeleteItem (plus Scan for `delete_for_runs`). A role with `CreateTable` lets a bug
   or a prompt-injected tool create resources outside IaC, with no backups, tags or alarms.
