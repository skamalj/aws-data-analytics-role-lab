# Mission 2 solution: The agent can't use its tools

```bash
patch -p1 < solutions/M2-gateway-tool-routing/fix.patch
./scripts/deploy.sh M2
```

## Fault 1: the gateway role can't invoke the orders Lambda

| | |
|---|---|
| Symptom | `tools/call` for `orders___get_order_status` returns an error mentioning `lambda:InvokeFunction` / AccessDenied. The orders Lambda logs **nothing** |
| Where | `data.aws_iam_policy_document.gateway` lists only `aws_lambda_function.inventory.arn` |
| Root cause | Three identities are involved: the **agent's runtime role** may call the gateway (`bedrock-agentcore:InvokeGateway`). The **gateway service role** (`credential_provider_configuration { gateway_iam_role {} }`) invokes the Lambda. The **Lambda's role** runs the code. Only the inventory function was in the gateway role's policy |
| Fix | `resources = [orders.arn, inventory.arn]`. That's exactly the two functions, not `*` |

## Fault 2: the orders Lambda doesn't strip the target prefix

| | |
|---|---|
| Symptom | Lambda log: `{"tool": "orders___get_order_status", ...}`, result `unknown tool 'orders___get_order_status'` |
| Where | `lambdas/orders.py`: `HANDLERS.get(tool)` uses the raw name |
| Root cause | A gateway combines many targets, so tool names are made unique as **`<target>___<tool>`** (three underscores). That full name is what clients see in `tools/list` and what Lambda receives in `context.client_context.custom["bedrockAgentCoreToolName"]`. The tool arguments arrive as the event |
| Fix | `tool = full_name.split("___", 1)[-1]`, the same as the inventory function already does |

## Fault 3: the tool description tells the model not to use it

| | |
|---|---|
| Symptom | Return requests get "please call support". `tools_used` is empty |
| Where | `start_return` `description = "Deprecated internal endpoint. Do not use; …"` |
| Root cause | The model only knows a tool through its **name, description and input schema**. A misleading description is a routing bug, just as a wrong ARN is |
| Fix | Describe what it does, when to use it, and its preconditions: "Start a return for a DELIVERED customer order … Use when a customer wants to return or send back an item." |

The Lambda still enforces the business rule (only `DELIVERED` orders), so O1002 is refused with a clear message. Don't rely on the description alone for rules.

## Debrief answers

1. `chat.py` (your IAM identity) → `InvokeAgentRuntime` → agent runs as the **runtime role** → SigV4
   `tools/call` → gateway authorizes it (`AWS_IAM`) → gateway invokes Lambda as the **gateway role** →
   Lambda runs as the **Lambda execution role**.
2. To avoid name collisions between targets. It shows up in `tools/list`, in the model's `toolUse.name`,
   in the Lambda client context, and in gateway logs.
3. Say what the tool does, when to use it and when not to, what each input means, and the preconditions.
   Keep it short and literal.
4. Use **OpenAPI/Smithy** to expose an existing REST API without writing code. Use an **MCP server**
   target when a team already runs an MCP server. Use **API Gateway** targets to reuse existing APIs with their auth.
   Use **Lambda** for custom logic and for gluing several back ends together.
