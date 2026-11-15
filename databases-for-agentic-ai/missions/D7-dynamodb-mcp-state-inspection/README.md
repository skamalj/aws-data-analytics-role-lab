# Mission D7: The memory inspector shows an empty brain

**Exam objective:** *Configure the DynamoDB MCP server for state inspection*
**Skills:** an MCP server for agent state on AgentCore Runtime, reading LangGraph checkpoints with the same library that wrote them ([`langgraph-dynamodb-checkpoint`](https://pypi.org/project/langgraph-dynamodb-checkpoint/)), read-only IAM for DynamoDB, safe output (bounded, redacted), the saver's create-if-missing behaviour
**Time:** 40 minutes  |  **Deploy:** `./scripts/deploy.sh D7` (doesn't need the base stack)

## Situation

Support engineers keep asking "what does Trail Desk *remember* about this customer?". The
platform team built an **agent-memory inspector**, an MCP server ([`mcp/server.py`](mcp/server.py))
that engineers plug into their coding agents. It reads the conversation checkpoints Trail Desk writes to
DynamoDB (`riverbend-d7-checkpoints`, the same design as D3) **through `DynamoDBSaver` itself**, so
the state is decoded exactly as the agent wrote it.

```
engineer's coding agent ──MCP──► AgentCore Runtime riverbend_d7_memory_inspector
                                    tools: describe_memory_table, list_threads, get_conversation, list_checkpoints, item_sizes, ...
                                    └─ DynamoDBSaver / DynamoDB API ──► riverbend-d7-checkpoints
```

## Setup and symptoms

```bash
./scripts/deploy.sh D7
pip install -r missions/D7-dynamodb-mcp-state-inspection/scenarios/requirements.txt
python3 missions/D7-dynamodb-mcp-state-inspection/scenarios/seed_conversations.py   # 5 real conversations
python3 missions/D7-dynamodb-mcp-state-inspection/scenarios/audit.py
```

The inspector reports errors, or an empty memory, although the seed script just wrote 5 threads.
Fix that first, then look at what it actually returns and what else it allows.

## Objectives

1. The inspector shows the agent's real memory: threads, latest conversation, checkpoints, item sizes.
2. It's strictly **read-only**: no tool, and no IAM permission, can change or delete agent memory or create tables.
3. Output is safe for transcripts: at most 20 messages, long content truncated, e-mail addresses and phone numbers redacted.
4. No stray resources are left behind.

## Done when

```
PASS  server lists its tools
PASS  inspector reads the agent's real memory table
PASS  list_threads shows the seeded conversations (5)
PASS  get_conversation is bounded (<= 20 messages, <= 20 KB)
PASS  get_conversation redacts e-mail addresses and phone numbers
PASS  no tool can change agent memory
PASS  inspector role is read-only on the memory table
PASS  no stray tables were created by the inspector
```

## Investigation toolkit

```bash
python3 -c "import sys; sys.path.insert(0,'common'); from mcp_client import Mcp; m=Mcp('missions/D7-dynamodb-mcp-state-inspection'); print(m.call('list_threads', {}))"
aws dynamodb list-tables --query "TableNames[?starts_with(@, 'riverbend-d7')]"
aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id <runtime_id> --query environmentVariables
aws logs tail "$(terraform -chdir=missions/D7-dynamodb-mcp-state-inspection/terraform output -raw log_group_hint)" --since 10m
```

## Hint ladder

<details><summary>Hint 1: where is it looking?</summary>Compare the table name the server is configured with to the one Terraform created. Then list the tables in your account. Read <code>_get_or_create_table()</code> in the saver's source: what happens when the table doesn't exist <i>and</i> the role may create tables?</details>
<details><summary>Hint 2: an inspector that can delete</summary>List the tools. Read the IAM policy. Which ones could change memory?</details>
<details><summary>Hint 3: what does an engineer see?</summary>Call <code>get_conversation</code> on <code>sizing-C00042-s1</code> and on <code>support-C00112-c1</code>. How big is the answer? What's in it?</details>

## Debrief questions

1. Why read checkpoints through `DynamoDBSaver` rather than parsing the items yourself?
2. Why does a missing `CreateTable` permission make a configuration error *safer*?
3. Which DynamoDB actions does this inspector really need?
4. Where should deleting a customer's memory (for example a GDPR request) live, if not in this server?
