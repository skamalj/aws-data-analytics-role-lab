# Mission 2: The agent can't use its tools

**Skills:** AgentCore Gateway, MCP (`tools/list`, `tools/call`), Lambda gateway targets and their event contract, tool schemas and descriptions, gateway service roles
**Time:** 40 minutes  |  **Deploy:** `./scripts/deploy.sh M2`

## Situation

Trail Desk should answer "where is my order?", "is this in stock?" and "I want to return
this" by calling Riverbend's back-end services. The services are two Lambda functions published
as **MCP tools** behind an **AgentCore Gateway**. The agent finds tools at runtime with
`tools/list`, gives them to the model, and runs the model's choice with `tools/call`. Requests
are signed with the agent's IAM role, because the gateway uses the `AWS_IAM` authorizer.

```
Trail Desk (runtime role) ──SigV4 MCP──► Gateway riverbend-m2-tools (role: riverbend-m2-gateway-*)
                                           ├─ target "orders"    ─► Lambda riverbend-m2-orders     tools: get_order_status, start_return
                                           └─ target "inventory" ─► Lambda riverbend-m2-inventory  tool:  check_stock
```

## Symptoms

```bash
python3 common/chat.py M2 "Is the Ridge Hiking Boot in stock at store S07?"   # works
python3 common/chat.py M2 "Where is my order O1001?"                           # fails
python3 common/chat.py M2 "Order O1003 arrived but the stove leaks, I want to return it."
```

- Stock questions work.
- Order questions fail. Run them with `--raw` to see the tool call and what came back.
- Return requests never even *try* a tool. The agent tells the customer to phone support.

## Objectives

1. `get_order_status` works for O1001, O1002 and O1003.
2. A delivered order (O1003) can be returned. The agent calls `start_return` and gives the customer an RMA id and label URL.
3. The gateway role may invoke **exactly** the two tool Lambdas, nothing more.
4. Fix the configuration and code. Don't bypass the gateway, for example by calling Lambda from the agent directly.

## Done when

```bash
python3 common/chat.py M2 "Where is my order O1001?"            # SHIPPED, TrailPost, TP-88231, ETA
python3 common/chat.py M2 "Return order O1003, the stove leaks"  # [tool] orders___start_return ... RMA-1003-01
python3 common/chat.py M2 "Return order O1002 please"            # politely refused: still processing
```

## Investigation toolkit

```bash
python3 common/chat.py M2 "..." --raw                    # the trace lists the gateway's tools and any tool errors
aws logs tail /aws/lambda/riverbend-m2-orders --since 10m
aws logs tail /aws/lambda/riverbend-m2-inventory --since 10m
aws bedrock-agentcore-control list-gateway-targets --gateway-identifier <gateway_id>
aws bedrock-agentcore-control get-gateway-target --gateway-identifier <gateway_id> --target-id <id>
aws iam get-role-policy --role-name <gateway_role_name> --policy-name invoke-tools
```

## Hint ladder

<details><summary>Hint 1: who calls the Lambda?</summary>

The agent never calls Lambda. The **gateway** does, with its own service role. Does the orders
Lambda even log an invocation? If not, the request never reached it.
</details>

<details><summary>Hint 2: what does the Lambda receive?</summary>

Once the Lambda is invoked, read its log line `{"tool": ...}`. Compare the tool name it
receives with the names in `HANDLERS`. The inventory Lambda handles the same thing differently.
</details>

<details><summary>Hint 3: why won't the model call start_return?</summary>

Models choose tools from the **name and description** in `tools/list`. Read the description the
gateway publishes for `start_return`.
</details>

## Red herrings

- `exception_level = "DEBUG"` is intentional for the lab. It makes tool errors readable.
- The MCP endpoint URL and the agent's `bedrock-agentcore:InvokeGateway` permission are correct.
- Changing the model won't help.

## Debrief questions

1. Draw the identities involved in one `tools/call`: caller → gateway → Lambda.
2. Why does the gateway prefix tool names with the target name, and where else does that prefix show up?
3. What makes a good tool description? Rewrite one of the three.
4. When would you choose an OpenAPI or Smithy target, or an MCP server target, instead of Lambda?
