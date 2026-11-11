# Mission D5 (capstone): Every question goes to the wrong place

**Skills:** routing between structured data, semantic retrieval and persistent state; tool descriptions as routing logic; trusted context vs model-supplied arguments; data scope per caller; per-tenant state isolation
**Time:** 50–60 minutes  |  **Needs:** `./scripts/deploy.sh base`, then `./scripts/deploy.sh D5`, then one sync:
`$(terraform -chdir=missions/D5-orchestration-capstone/terraform output -raw sync_command)`

## Situation

Everything from D1–D3 now works on its own, and the team has combined it into **one LangGraph agent**
([`agent/app.py`](agent/app.py)):

| Capability | Component (already fixed) |
|---|---|
| Structured data | `orders___get_order` → Gateway → Lambda ([`lambdas/orders.py`](lambdas/orders.py)) → `reporting.order_summary` as `trail_desk_app` |
| Semantic retrieval | `search_manuals` → Knowledge Base on pgvector (`bedrock_kb.d5_chunks`) |
| Persistent state | `DynamoDBSaver` (`langgraph-dynamodb-checkpoint`) with TTL and a reducer |

The web app signs customers in and sends `customer_id` together with `conversation_id` and the prompt.
Each piece passes its own tests. **Together**, the assistant misbehaves.

## Symptoms

```bash
python3 missions/D5-orchestration-capstone/scenarios/capstone.py
```

| Check | What goes wrong |
|---|---|
| 1. Order questions use the order tool | "Where is my order O1003?" gets an answer from the manuals (or no tool at all) |
| 2. Care questions use the manuals | usually fine |
| 3. Data scope | customer C00112 can read order O1001, which belongs to C00038 |
| 4. State isolation | C00038 opens a conversation with the same id as C00112's and is told C00112's locker code |

## Objectives

1. Order questions are answered by `get_order`, and product, care and policy questions by `search_manuals`.
2. Order data is restricted to the **signed-in** customer, enforced in the tool and its query, not by asking the model nicely.
3. Conversation state can never be shared between customers.
4. No new permissions: the database identity, IAM roles and checkpointer setup stay as they are.

## Done when

```
PASS  order status is answered by orders___get_order
PASS  care question is answered by search_manuals
PASS  C00112 cannot read C00038's order O1001
PASS  C00038 does not get C00112's conversation
4/4 checks passed
```

Check 1 depends on the model choosing a tool. If it still fails occasionally after your fix, improve the descriptions further, the way you would for any production agent.

## Investigation toolkit

```bash
python3 common/chat.py D5 "Where is my order O1003?" --customer C00112 --conversation t1 --raw
aws logs tail /aws/lambda/riverbend-d5-orders --since 10m               # which arguments did the tool receive?
aws bedrock-agentcore-control list-gateway-targets --gateway-identifier <id>
aws dynamodb scan --table-name riverbend-d5-checkpoints --projection-expression PK --max-items 20   # thread ids
```

## Hint ladder

<details><summary>Hint 1: routing</summary>

The model chooses tools only from their **descriptions**. Read both descriptions as if you were the model, for the question "Where is my order O1003?". One of them claims the other's job, and the other one says it isn't for customers.
</details>

<details><summary>Hint 2: who decides which customer?</summary>

Look at the Lambda's log line for check 3. Which customer's data does the query return, and where could the customer id come from? `riverbend_graph.gateway_tools(..., inject=...)` exists for a reason.
</details>

<details><summary>Hint 3: whose thread is it?</summary>

Look at the thread ids (`PK`) in the checkpoint table. What do two customers using the same conversation id share?
</details>

## Red herrings

- The knowledge base, its sync and the checkpointer are fine.
- Don't change the model. Routing problems are usually description problems.

## Debrief questions

1. Write the routing table for this agent: request type → capability → tool → identity used.
2. Why must the customer id be injected by the application and checked in SQL, rather than added to the system prompt?
3. Which other controls from the guide would you add next (allowlists, timeouts, bounded retries, idempotency, output redaction), and where?
4. How would you test routing continuously as tools and models change?
