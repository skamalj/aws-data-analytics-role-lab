# Challenge S2 solution: The research agent has no identity

```bash
patch -p1 < solutions/S2-self-hosted-workload-identity/fix.patch
./scripts/deploy.sh S2
python3 missions/S2-self-hosted-workload-identity/scenarios/check.py     # allow ~5 minutes for SSM registration after the fix
```

| # | Symptom | Fault | Fix |
|---|---|---|---|
| 1 | Run Command: `InvalidInstanceId` / host not in Fleet Manager | The instance role lacks **`AmazonSSMManagedInstanceCore`**, so the SSM Agent can't register | Attach the managed policy. Keep IMDSv2 required and no SSH |
| 2 | `ResourceNotFoundException` for `larchmont-s2-research-agent` | The workload identity was never created. Runtime creates identities for **its** agents. A self-hosted agent needs one provisioned explicitly | `aws_bedrockagentcore_workload_identity` (`CreateWorkloadIdentity`) with `team = research` tags |
| 3 | `AccessDeniedException` on `GetWorkloadAccessToken` | The role allows only **`GetWorkloadAccessTokenForJWT`**, which is for agents acting for a user who presented a JWT (S5). The research agent acts for itself | `bedrock-agentcore:GetWorkloadAccessToken` on the directory and **this** identity only |
| 4 | Token obtained, `GetResourceApiKey` fails with access denied | The token vault stores the key in **Secrets Manager** (`bedrock-agentcore-identity!default/apikey/…`) and reads it with the caller's permissions | `secretsmanager:GetSecretValue` on exactly that secret ARN (base output `market_data_secret_arn`) |

The flow, for the exam:

```
EC2 instance role creds ─► GetWorkloadAccessToken(workloadName)            ─► workload access token (short-lived)
                       ─► GetResourceApiKey(workloadIdentityToken, provider) ─► API key (never stored on the host)
```

Variants:
- `GetWorkloadAccessTokenForUserId`: the agent acts for a user the caller vouches for.
- `GetWorkloadAccessTokenForJWT`: the agent acts for a user whose JWT is verified against the identity's allowed issuers.
- For OAuth resources, `GetResourceOauth2Token` with `oauth2Flow = M2M`, or `USER_FEDERATION` plus `allowedResourceOauth2ReturnUrls` on the workload identity.
