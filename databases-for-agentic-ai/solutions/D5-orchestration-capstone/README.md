# Mission D5 solution: Every question goes to the wrong place

```bash
patch -p1 < solutions/D5-orchestration-capstone/fix.patch
./scripts/deploy.sh D5
python3 missions/D5-orchestration-capstone/scenarios/capstone.py
```

## Fault 1: tool descriptions route order questions to the manuals

| | |
|---|---|
| Where | `get_order`: *"Internal raw order record lookup (staff tooling)."* `search_manuals`: *"…answer customer questions about orders, deliveries, shipping status, returns…"* |
| Root cause | Tool descriptions **are** the routing logic. One tool disowned customer use, and the other claimed its territory |
| Fix | `get_order`: what it returns, and *"use for any question about a specific order"*. `search_manuals`: manuals and **policies**, and explicitly *"not for the status or contents of a specific order"* |

Good descriptions say what the tool is for, what it isn't for, and its inputs. Overlap between tools is the most common cause of misrouting.

## Fault 2: data scope comes from nowhere, or from the model

| | |
|---|---|
| Symptom | C00112 reads O1001. The Lambda log shows `{"order_id": "O1001"}`, or a model-invented `customer_id` |
| Root cause | The query filtered only on `order_id`. Nothing tied the result to the signed-in customer, and a model-supplied `customer_id` would be just as untrustworthy |
| Fix | Three parts: 1. `app.py` **injects** `customer_id` from the request context into every gateway call (`inject=scope_to_caller`), overwriting anything the model put there. 2. The Lambda **requires** a valid `customer_id`. 3. The SQL filters `WHERE order_id = :id AND customer_id = :cid`, so a foreign order is simply "not found" |

## Fault 3: conversation state is keyed without the customer

| | |
|---|---|
| Symptom | C00038, using conversation id `help-…`, resumes C00112's thread and its history |
| Root cause | `thread_id = "support-" + conversation_id`. Conversation ids are client-supplied, and they can collide or be guessed |
| Fix | `thread_id = f"support-{customer_id}-{conversation_id}"`, and reject requests without a signed-in customer. This is the D3 debrief question, answered |

## The routing table (debrief 1)

| Request type | Capability | Tool | Identity |
|---|---|---|---|
| Status or contents of *my* order | Structured data | `orders___get_order` | runtime role → gateway role → Lambda role → DB `trail_desk_app` (reporting views), scoped by injected `customer_id` |
| Care, use, safety, warranty or return *policy* | Semantic retrieval | `search_manuals` | runtime role (`bedrock:Retrieve`), with the KB → DB as `bedrock_kb_user` |
| Continuing an earlier conversation | Persistent state | checkpointer (not a tool) | runtime role → DynamoDB table, thread scoped per customer |
| Engineers inspecting data | Diagnostics | MCP server (D4), not part of this agent | `diag_readonly` |

## Debrief answers

2. The model is not a security boundary. A prompt can be overridden by injected text, while an injected argument plus a SQL predicate can't.
   Authorization belongs in code and data access paths that the model doesn't control.
3. An **allowlist** of tools per request type. **Timeouts** on every tool (Lambda 30 s, statement timeout 5 s) and the graph's `recursion_limit`.
   **Bounded retries** with backoff on throttling and Aurora resume. **Idempotency keys** on actions with side effects (returns).
   **Output redaction** in tools, as in D4. **Explicit failures**: friendly messages to the model, details only in logs.
4. Keep a routing test set (like `capstone.py`) of representative questions with the expected tool. Run it in CI and whenever you change a model or
   description, track the pass rate over time, and alert on regressions. AgentCore observability traces show which tool each production request chose.
