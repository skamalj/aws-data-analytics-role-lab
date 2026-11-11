# Mission 4 solution: Every chat starts from zero

```bash
patch -p1 < solutions/M4-agentcore-memory/fix.patch
./scripts/deploy.sh M4
python3 common/chat.py M4 --actor alex --new-session "Hi! I'm Alex. I wear EU size 43 boots, I hike mostly in rain and my budget is under 150 euros."
sleep 120
python3 common/chat.py M4 --actor alex --new-session "Can you recommend a jacket for me?"
```

You must have a new conversation after the fix. Strategies only process events created after they exist.

## Fault 1: the role can't read long-term memory

| | |
|---|---|
| Symptom | `{"error": "AccessDeniedException: … not authorized to perform: bedrock-agentcore:RetrieveMemoryRecords on resource: …memory/riverbend_m4_customer_memory-…"}` |
| Where | Agent policy `Memory` allows `CreateEvent`, `ListEvents`, `GetEvent` |
| Fix | Add `bedrock-agentcore:RetrieveMemoryRecords`, still on the memory ARN only |

## Fault 2: there is no strategy that captures customer preferences

| | |
|---|---|
| Symptom | No more errors, but `long_term_records: 0` in every new session. `list-memory-records` shows only `/customers/alex/sessions/<id>` summaries |
| Root cause | Long-term memory only contains what a **strategy** extracts. `SUMMARIZATION` condenses one session into the `{sessionId}` namespace. Nothing extracts durable facts about the **customer** |
| Fix | `aws_bedrockagentcore_memory_strategy "preferences"`, `type = "USER_PREFERENCE"`, `namespace_templates = ["/customers/{actorId}/preferences"]` |

## Fault 3: the agent reads a per-session namespace

| | |
|---|---|
| Symptom | Even with the strategy, the trace shows `memory_namespace: /customers/riverbend-<uuid>/preferences`, which is different for every chat |
| Where | Runtime env `MEMORY_NAMESPACE = "/customers/{sessionId}/preferences"` |
| Root cause | Preferences belong to the **actor** and must be found again from any session. The read namespace must match the strategy's namespace template |
| Fix | `MEMORY_NAMESPACE = "/customers/{actorId}/preferences"` |

## Debrief answers

1. **Short-term memory** is the raw turns of the current session (`CreateEvent`/`ListEvents`). It keeps the
   conversation coherent and expires after `event_expiry_duration`. **Long-term memory** is extracted, deduplicated
   records (`RetrieveMemoryRecords`, semantic search inside a namespace) that outlive sessions.
2. Namespaces partition records. `{actorId}` scopes them to a customer across all sessions. With `{sessionId}`,
   every chat would get a new, empty namespace, which is exactly the bug.
3. `SEMANTIC` stores factual knowledge from conversations ("Alex's last trip was the Kungsleden"), while
   `USER_PREFERENCE` stores likes and constraints. Many assistants use both, plus `SUMMARIZATION`.
4. Records are keyed by `actorId`, and the agent only queries its own actor's namespace. The **caller must
   authenticate the user** and pass a trustworthy `actor_id`. In production, derive it from the verified JWT
   (Mission 1), never from free text. For stronger isolation, use IAM condition keys on namespaces, or one memory per tenant.
