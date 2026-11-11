# Mission D3: Resume fails, and then the state explodes

**Skills:** persistent agent state in Amazon DynamoDB, LangGraph checkpointers ([`langgraph-dynamodb-checkpoint`](https://pypi.org/project/langgraph-dynamodb-checkpoint/)), `thread_id` design, key schemas, TTL, DynamoDB's 400 KB item limit, bounded message history ([`agentstate-reducer`](https://pypi.org/project/agentstate-reducer/)), least privilege
**Time:** 45–60 minutes  |  **Deploy:** `./scripts/deploy.sh D3` (doesn't need the base stack)

## Situation

Trail Desk's returns assistant is a **LangGraph** agent on AgentCore Runtime. A return takes
several steps: look up the order, check eligibility, ask for the reason, create the return. Customers often
leave half-way and come back hours later. By then their runtime session is long gone.

To survive that, every step of the graph is checkpointed in **DynamoDB** with
`langgraph-dynamodb-checkpoint` (`DynamoDBSaver`). The platform team owns the table in Terraform.
The agent's role may read and write items but must **not** create or delete tables. Checkpoints
should expire after 7 days.

```
web app ──(prompt, conversation_id, customer_id)──► AgentCore Runtime session (short-lived)
                                                       └─ LangGraph graph: model ⇄ tools
                                                            └─ DynamoDBSaver ──► table riverbend-d3-checkpoints
                                                                                 one item per checkpoint + pending writes
```

Code: [`agent/app.py`](agent/app.py) (graph, tools, checkpointer) and
[`common/graph/riverbend_graph.py`](../../common/graph/riverbend_graph.py) (graph wiring, you don't need to change it).

## Symptoms

```bash
python3 common/chat.py D3 "Hi, I'd like to return my order O2003." --conversation test-1 --customer C00042
python3 missions/D3-persistent-agent-state/scenarios/resume.py      # leave and come back
python3 missions/D3-persistent-agent-state/scenarios/long_chat.py   # 20 turns with ~30 KB tool results
python3 missions/D3-persistent-agent-state/scenarios/check_ttl.py   # are checkpoints going to expire?
```

The first request fails straight away. Fix that, and the next failure appears. Several things are
wrong, in the Terraform **and** in `agent/app.py`.

## Objectives

1. Trail Desk answers, and every graph step is checkpointed in the Terraform-owned table.
2. `resume.py` passes: the return started in session A is completed in session B.
3. `long_chat.py` passes all 20 turns, and the stored checkpoints stay well below DynamoDB's item size limit.
4. `check_ttl.py` passes: every checkpoint item expires about 7 days after it was written.
5. Least privilege: the agent's role gets **no** `dynamodb:CreateTable`, `DeleteTable` or `dynamodb:*`.
   Don't let the saver create its own table either; the table stays in Terraform.

## Done when

```
RESUME: PASS - the return for O2003 was created in the new session
LONG CHAT: PASS - 20 turns without errors
TTL: PASS
```

## Investigation toolkit

```bash
T=$(terraform -chdir=missions/D3-persistent-agent-state/terraform output -raw checkpoint_table)
aws dynamodb describe-table --table-name $T --query 'Table.KeySchema'
aws dynamodb describe-time-to-live --table-name $T
aws dynamodb scan --table-name $T --max-items 5 --projection-expression "PK, SK, #t" --expression-attribute-names '{"#t":"ttl"}'
aws logs tail "$(terraform -chdir=missions/D3-persistent-agent-state/terraform output -raw log_group_hint)" --since 15m
pip download langgraph-dynamodb-checkpoint==0.5.0 --no-deps -d /tmp/saver   # read the saver's source
```

## Hint ladder

<details><summary>Hint 1: before the first checkpoint is written</summary>

The saver does something to the table **when it's constructed**, before any read or write. Look at
`_get_or_create_table()` in its source. Which API call is that, and which DynamoDB actions does the role allow?
</details>

<details><summary>Hint 2: the table and the saver must agree</summary>

Read the saver's README section "Table Structure", or what `put()` writes. Then compare it with `describe-table`.
</details>

<details><summary>Hint 3: which state does a new session load?</summary>

LangGraph loads state by `config["configurable"]["thread_id"]`. Print the thread id in the trace for
two visits. A runtime session id and a conversation id aren't the same thing.
</details>

<details><summary>Hint 4: the item limit</summary>

Every checkpoint stores the **whole** message history, tool results included. With 30 KB fit guides, how many
turns does it take to reach 400 KB? The package's own start-up log line tells you the fix.
Also read what `ttl_seconds` does, and what TTL the saver enables on a table it **didn't** create.
</details>

## Red herrings

- The model, prompt and tools are fine. `fit_guide` is meant to return a long text.
- Throughput isn't the problem. The table is on-demand.
- `point_in_time_recovery` doesn't matter here.

## Debrief questions

1. Why is the conversation id, not the runtime session id, the right `thread_id`? When would you use `customer_id + conversation_id`?
2. What exactly is in a checkpoint, and why does it grow on every turn?
3. Pruning the stored history loses old turns. How would you keep what matters? (Look at `on_prune` and `memory_namespace`.)
4. TTL deletion is asynchronous. What does that mean for code that reads checkpoints?
5. Which DynamoDB actions does the saver need, and why is `CreateTable` dangerous in production?
