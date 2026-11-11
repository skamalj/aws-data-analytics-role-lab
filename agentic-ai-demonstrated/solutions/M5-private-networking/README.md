# Mission 5 solution: Lights out on the public internet

```bash
patch -p1 < solutions/M5-private-networking/fix.patch
./scripts/deploy.sh M5
```

## Fault 1: private DNS is off on the Bedrock interface endpoint

| | |
|---|---|
| Symptom | `ConnectTimeoutError … bedrock-runtime.<region>.amazonaws.com` |
| Where | `aws_vpc_endpoint.bedrock_runtime.private_dns_enabled = false` |
| Root cause | Without private DNS, the regional service name still resolves to **public** IPs. The subnets have no route to the internet, so the TCP connect times out. The endpoint exists but nothing uses it, unless the client is configured with the endpoint-specific DNS name (`vpce-…bedrock-runtime…vpce.amazonaws.com`) |
| Fix | `private_dns_enabled = true`. Route 53 then serves a private hosted zone that maps the service name to the endpoint ENIs (this needs the VPC's DNS support + DNS hostnames, which are already on) |

## Fault 2: the endpoint's security group allows the wrong source

| | |
|---|---|
| Symptom | Still a connect timeout after fix 1. The name now resolves to 10.20.x.x, but the packets are dropped |
| Where | `aws_security_group.endpoints` ingress 443 from `10.20.100.0/24`, while the agent ENIs are in `10.20.1.0/24` and `10.20.2.0/24` |
| Fix | Allow 443 **from the agent's security group** (`security_groups = [aws_security_group.agent.id]`). That follows the ENIs wherever AgentCore places them, and keeps everything else in the VPC out |

## Fault 3: the DynamoDB gateway endpoint isn't on the route table

| | |
|---|---|
| Symptom | Chat works. Store questions give a `tool_error` with `ConnectTimeoutError … dynamodb.<region>.amazonaws.com` |
| Where | `aws_vpc_endpoint.dynamodb` has no `route_table_ids` |
| Root cause | Gateway endpoints (S3, DynamoDB) don't use DNS or ENIs. They add a route `pl-xxxx (DynamoDB prefix list) → vpce-…` to the route tables you associate. With no association there's no route |
| Fix | `route_table_ids = [aws_route_table.private.id]` |

## Debrief answers

1. **Interface endpoint**: ENIs in your subnets with private IPs, reached through DNS. Billed per hour per AZ plus per GB.
   Available for most services. **Gateway endpoint**: route-table entries to a prefix list. Free. Only S3 and DynamoDB.
2. AgentCore manages the ENIs, so their IPs can change and subnets can be added. An SG reference expresses
   "the agent" rather than an address range. It's also tighter: other workloads in the same subnets stay out.
3. `bedrock-agentcore` (Memory data plane, Gateway invocations), `bedrock-agent-runtime` (Knowledge Base `Retrieve`),
   S3 (gateway) for any S3 access, `logs`/`monitoring` if the code calls CloudWatch itself, `sts` if it assumes roles,
   and `secretsmanager`/`ssm` for secrets.
4. Look at the route tables: no `0.0.0.0/0` route. Add VPC Flow Logs, and watch for REJECTs to public IPs. Use Reachability Analyzer
   to the internet gateway (none exists). Have the agent try `https://checkip.amazonaws.com`: it should time out.
