# Challenge S4 solution: The rebalancing service can't reach its agent

```bash
patch -p1 < solutions/S4-sigv4-rebalancing-path/fix.patch
./scripts/deploy.sh S4
python3 missions/S4-sigv4-rebalancing-path/scenarios/check.py
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Every SigV4 call is refused with an authorization-method error | The template brought a **custom JWT authorizer** with it. A runtime with `authorizer_configuration` accepts only bearer tokens | Remove `authorizer_configuration`: the runtime then authorizes callers with IAM (SigV4) |
| 2 | `AccessDeniedException` for the service | The policy's resource is `runtime/larchmont_s4_rebalancer`, but runtime ARNs use the runtime **ID** (`larchmont_s4_rebalancer-AbCd123456`) | Reference `agent_runtime_arn` (and `…/*` for its endpoints) |
| 3 | Still denied, only when `runtimeUserId` is sent | Acting for a user needs **`bedrock-agentcore:InvokeAgentRuntimeForUser`** in addition to `InvokeAgentRuntime` | Grant it to the rebalancing service only. The ops console keeps its explicit Deny |
| 4 | The agent answers `credential: failed` (AccessDenied) | The execution role has `GetResourceApiKey` (copied from an API-key agent). OAuth2 tokens come from **`GetResourceOauth2Token`** | Swap the action. The provider's client secret (`ledger_secret_arn`) is already readable |

Why `InvokeAgentRuntimeForUser` matters:
- With a user ID, the runtime gets a workload access token **for that user** (`GetWorkloadAccessTokenForUserId`). The agent can then reach
  user-scoped OAuth tokens in the vault.
- AgentCore doesn't verify the user ID. It trusts the caller.
- So the permission must be held only by services you trust to name users. Deny it explicitly everywhere else, and audit it (S6).

The two inbound patterns side by side:

| | Humans via a portal (S3, S5) | Internal service (S4) |
|---|---|---|
| Inbound auth | Custom JWT authorizer (Cognito) | IAM / SigV4 |
| Who is the user | Verified token claims | `runtimeUserId`, vouched for by the caller |
| Workload token | `GetWorkloadAccessTokenForJWT` | `GetWorkloadAccessTokenForUserId` |
| Least privilege | `allowed_clients` + `allowed_scopes` | IAM on the runtime ARN + `InvokeAgentRuntimeForUser` |
