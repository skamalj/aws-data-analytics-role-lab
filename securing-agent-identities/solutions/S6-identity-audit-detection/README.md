# Challenge S6 solution: Nobody noticed

```bash
patch -p1 < solutions/S6-identity-audit-detection/fix.patch
./scripts/deploy.sh S6
python3 missions/S6-identity-audit-detection/scenarios/simulate_incident.py
# wait ~15 minutes
python3 missions/S6-identity-audit-detection/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | The log group stays empty. `get-trail-status` shows a CloudWatch Logs delivery error | The delivery role has `logs:CreateLogStream` but not **`logs:PutLogEvents`** | Grant both on `<log group ARN>:*` |
| 2 | Denied calls and re-tags never reach the logs | The management selector has `readOnly = true`: only reads are recorded. `TagResource`, `UpdateWorkloadIdentity` and `DeleteWorkloadIdentity` are writes | Drop the `readOnly` filter (or use `false`) so write events are recorded |
| 3 | Token operations (`GetWorkloadAccessToken*`) aren't recorded at all | They're **data events**, which trails never log unless selected | A second advanced selector: `eventCategory = Data`, `resources.type = AWS::BedrockAgentCore::WorkloadIdentity` |
| 4 | `TokenAccessDenied` never counts | The filter tests `eventSource = "bedrock.amazonaws.com"` (Bedrock models), not `bedrock-agentcore.amazonaws.com` | Fix the event source. `errorCode = "AccessDenied*"` covers `AccessDenied` and `AccessDeniedException` |
| 5 | The tampering alarm stays at `INSUFFICIENT_DATA` | The alarm watches `WorkloadIdentityTamper`, a metric no filter emits (the filter emits `WorkloadIdentityTampering`) | Match the metric name and namespace exactly |

**Check before you rely on fix 3.** As of writing, AWS documents AgentCore data events for Gateway (`AWS::BedrockAgentCore::Gateway`). The
CloudTrail resource-type reference also lists `AWS::BedrockAgentCore::WorkloadIdentity` and `WorkloadIdentityDirectory`.
- If your Region rejects the selector, check CloudTrail's "data events" table for the current AgentCore types.
- Denied calls are still caught by the management selector once fix 2 is in place.

What to alarm on, beyond this lab:
- `InvokeAgentRuntimeForUser` from unexpected principals. The user ID isn't verified (S4).
- `CreateWorkloadIdentity` / `DeleteWorkloadIdentity` outside the deployment pipeline's role.
- `GetResourceOauth2Token` / `GetResourceApiKey` failures per workload, and changes to credential providers (`Update*CredentialProvider`).
- Use CloudTrail Lake or Athena over the S3 archive for investigations: the CloudWatch filters are for detection, not forensics.
