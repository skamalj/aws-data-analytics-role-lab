# Mission 4: Every chat starts from zero

**Skills:** AgentCore Memory, short-term events vs long-term memory records, memory strategies (summary, user preference, semantic), namespaces and `{actorId}`/`{sessionId}`, memory data-plane permissions
**Time:** 35–45 minutes  |  **Deploy:** `./scripts/deploy.sh M4`

## Situation

Loyal customers complain that Trail Desk "forgets everything". They explain their boot size,
budget and that they only hike in wet weather, and the next day they have to explain it all again.
The agent uses **AgentCore Memory**:

- On every turn it writes the user and assistant messages as an **event** (`CreateEvent`), keyed by `actorId` (the customer) and `sessionId` (one chat).
- Before answering it loads the current session's recent events (`ListEvents`) **and** searches **long-term memory records** (`RetrieveMemoryRecords`) in the namespace given by `MEMORY_NAMESPACE`.
- Long-term records are produced **asynchronously** by the memory's **strategies**, which read new events and extract summaries, preferences or facts into namespaces.

```
chat (actor "alex", session A) ──► CreateEvent ──► memory riverbend_m4_customer_memory
                                                      ├─ short-term events (actor alex, session A)
                                                      └─ strategies (async, ~1 min) ──► long-term records in namespaces
new chat (actor "alex", session B) ──► RetrieveMemoryRecords(namespace = MEMORY_NAMESPACE) ──► "what you remember about this customer"
```

## Symptom

```bash
python3 common/chat.py M4 --actor alex --new-session "Hi! I'm Alex. I wear EU size 43 boots, I hike mostly in rain and my budget is under 150 euros."
python3 common/chat.py M4 --actor alex "Which boots would suit me?"                 # same session
# wait 2 minutes, then a brand-new session:
python3 common/chat.py M4 --actor alex --new-session "Can you recommend a jacket for me?"
```

Look at the `[trace]` lines (`long_term_records`, `short_term_turns`) and at any errors.

## Objectives

1. No memory errors on any turn.
2. In a **new session**, Trail Desk knows Alex's size, rain preference and budget, without being told again.
3. A **different** customer (`--actor sam`) doesn't get Alex's preferences.
4. Keep the session-summary strategy, and keep the IAM policy limited to this memory resource.

## Done when

```bash
python3 common/chat.py M4 --actor alex --new-session "Can you recommend a jacket for me?"
#   [trace] {"memory_namespace": "/customers/alex/preferences", "long_term_records": 2+}
#   answer mentions rain / waterproof and the budget
python3 common/chat.py M4 --actor sam --new-session "Can you recommend a jacket for me?"
#   [trace] long_term_records: 0, generic answer
```

## Investigation toolkit

```bash
MEM=$(terraform -chdir=missions/M4-agentcore-memory/terraform output -raw memory_id)
aws bedrock-agentcore-control get-memory --memory-id $MEM --query 'memory.strategies'
aws bedrock-agentcore list-events --memory-id $MEM --actor-id alex --session-id "$(cat .session-M4)"
aws bedrock-agentcore list-memory-records --memory-id $MEM --namespace /customers/alex/
aws bedrock-agentcore list-sessions --memory-id $MEM --actor-id alex
```

## Hint ladder

<details><summary>Hint 1: the error comes first</summary>

The agent calls three memory data-plane APIs. Compare them with the actions in the `Memory`
statement of the runtime role's policy.
</details>

<details><summary>Hint 2: what would produce a preference record?</summary>

`list-memory-records` returns only session summaries. Which strategy type extracts durable
facts about a *user*, and which namespace would it write to?
</details>

<details><summary>Hint 3: whose memories are you reading?</summary>

Look at the namespace in the trace for two different sessions of the same customer. What
placeholder should identify *the customer* rather than *the chat*?
</details>

## Red herrings

- `event_expiry_duration = 30` only controls how long raw events are kept.
- The session-summary strategy works fine. It's just not what answers "what do I know about this customer".
- Long-term extraction is asynchronous. After a fix, have a *new* conversation and wait 1–2 minutes. Events written before a strategy existed aren't processed by it.

## Debrief questions

1. Short-term vs long-term memory: what is each one for, and which API reads each?
2. Why is the namespace a template with `{actorId}`, and what would go wrong with `{sessionId}` in it for preferences?
3. When would you add a `SEMANTIC` strategy as well as `USER_PREFERENCE`?
4. How does this design keep one customer's memories away from another? What must the *caller* guarantee about `actor_id`?
