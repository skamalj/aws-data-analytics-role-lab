# Mission 5: Lights out on the public internet

**Skills:** AgentCore Runtime VPC mode, AWS PrivateLink interface endpoints, private DNS, security groups for endpoints, gateway endpoints and route tables, diagnosing timeouts
**Time:** 45 minutes  |  **Deploy:** `./scripts/deploy.sh M5` (VPC endpoint creation takes 2–3 minutes)

## Situation

Riverbend's security review has a new rule: **agents must not have any internet path.** Trail
Desk now runs in **VPC mode**. AgentCore places its network interfaces in two private subnets
with no internet gateway and no NAT gateway. Everything the agent talks to must be reached privately:

- **Amazon Bedrock** (the Converse API) through an **interface endpoint** for `bedrock-runtime`
- **Amazon DynamoDB** (the store directory, via the `store_info` tool) through a **gateway endpoint**

The network team built the VPC and endpoints in Terraform and went home.

```
VPC 10.20.0.0/16 (no IGW, no NAT)
 ├─ private subnet 10.20.1.0/24 ─┐   AgentCore Runtime ENIs (SG riverbend-m5-agent-*)
 ├─ private subnet 10.20.2.0/24 ─┤        │ HTTPS
 │                               │        ├──► interface endpoint com.amazonaws.<region>.bedrock-runtime (SG riverbend-m5-endpoints-*)
 │   route table riverbend-m5-private     └──► DynamoDB gateway endpoint (route via prefix list)
```

## Symptom

```bash
python3 common/chat.py M5 "Hello"
python3 common/chat.py M5 "What are the opening hours of store S07?"
```

The first request returns an error after a few seconds, like
`ConnectTimeoutError: Connect timeout on endpoint URL: "https://bedrock-runtime.<region>.amazonaws.com/model/.../converse"`.
The agent code sets a 5-second connect timeout and no retries, so network faults show up quickly.

## Objectives

1. Trail Desk answers normal questions (Bedrock reachable privately).
2. Trail Desk answers store questions from DynamoDB.
3. Still **no** internet gateway, NAT gateway or public IPs. Don't switch the runtime to `PUBLIC`.
4. Endpoint access is as tight as practical: only the agent's ENIs can reach the interface endpoint.

## Done when

```bash
python3 common/chat.py M5 "Hello"                                       # answer, no error
python3 common/chat.py M5 "What are the opening hours of store S07?"    # [tool] store_info {"store_id": "S07"}  Mon-Sat 10:00-19:00
```

## Investigation toolkit

```bash
terraform -chdir=missions/M5-private-networking/terraform output
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<vpc_id> \
  --query 'VpcEndpoints[].{svc:ServiceName,type:VpcEndpointType,dns:PrivateDnsEnabled,rt:RouteTableIds,sg:Groups[].GroupId}'
aws ec2 describe-security-groups --group-ids <endpoint_security_group> --query 'SecurityGroups[].IpPermissions'
aws ec2 describe-route-tables --route-table-ids <route_table_id> --query 'RouteTables[].Routes'
aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=<vpc_id> \
  --query 'NetworkInterfaces[].{ip:PrivateIpAddress,desc:Description,sg:Groups[].GroupId}'
```

*Reachability Analyzer* (VPC console) from an agent ENI to the endpoint ENI on port 443 is a great tool here.

## Hint ladder

<details><summary>Hint 1: which IP does the SDK connect to?</summary>

The SDK always calls `bedrock-runtime.<region>.amazonaws.com`. Inside the VPC, that name only
resolves to the endpoint's private IPs if one specific endpoint setting is on. Otherwise it
resolves to public IPs, and there's no route to those.
</details>

<details><summary>Hint 2: the endpoint is also a network interface</summary>

Interface endpoints have security groups. Which source does the endpoint SG allow on 443, and
which subnets are the agent's ENIs actually in?
</details>

<details><summary>Hint 3: gateway endpoints don't have ENIs</summary>

A gateway endpoint works by adding a route (destination: the DynamoDB prefix list) to route tables.
Which route tables is this one attached to?
</details>

## Red herrings

- `enable_dns_support` and `enable_dns_hostnames` are already on, and both are needed.
- The agent SG's egress rule (443 to anywhere) is fine. Without an internet route, "anywhere" only means private targets.
- IAM permissions for Bedrock and DynamoDB are correct.

## Debrief questions

1. Interface endpoint vs gateway endpoint: how does traffic reach each one, and what does each cost?
2. Why is referencing the agent's **security group** better than a CIDR in the endpoint SG?
3. Which other endpoints would this agent need if it also used AgentCore Memory, a Knowledge Base or a Gateway (Missions 2–4)?
4. How would you *prove* the agent has no internet path?
