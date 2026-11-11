# Mission 1 solution: The front door is locked

Apply the reference fix from the kit root, then redeploy:

```bash
patch -p1 < solutions/M1-identity-front-door/fix.patch
./scripts/deploy.sh M1
python3 common/chat.py M1 "Hi! What can you help me with?"
```

## Fault 1: the app client may not request the `invoke` scope

| | |
|---|---|
| Symptom | `[token] … HTTP 400 {"error":"invalid_scope"}` |
| Where | `aws_cognito_user_pool_client.console.allowed_oauth_scopes = ["riverbend-agent/status"]` |
| Root cause | In the client-credentials flow, Cognito only issues scopes the app client is **allowed** to request. The console asks for `riverbend-agent/invoke`, but the client was only granted `status` |
| Fix | `allowed_oauth_scopes = ["riverbend-agent/invoke"]` |

## Fault 2: the authorizer checks a claim Cognito M2M tokens don't have

| | |
|---|---|
| Symptom | Token works, then the runtime returns **HTTP 403** (authorization failed / claim mismatch) |
| Where | `custom_jwt_authorizer.allowed_audience = [<client id>]` |
| Root cause | A Cognito **access token** from the client-credentials grant carries `client_id`, `scope`, `token_use = access` and `iss`. It has **no `aud` claim**. (ID tokens have `aud`, but M2M flows don't produce ID tokens.) An authorizer that requires `aud` rejects every token |
| Fix | `allowed_clients = [<console client id>]`, so the runtime checks the `client_id` claim |

What `--show-token` shows after fix 1:

```json
{ "sub": "…", "token_use": "access", "scope": "riverbend-agent/invoke",
  "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_XXXX",
  "client_id": "…", "exp": 1700000000, "iat": 1699996400, "version": 2 }
```

The authorizer still checks:
- the signature, using the JWKS found through `discovery_url`
- `iss`, which must match the discovery document
- expiry
- `client_id`, through `allowed_clients`
- `scope`, through `allowed_scopes`

## Fault 3: the execution role can't use the inference profile

| | |
|---|---|
| Symptom | The runtime answers, but the body is `{"error": "AccessDeniedException: … not authorized to perform: bedrock:InvokeModel on resource: arn:aws:bedrock:us-west-2:<acct>:inference-profile/us.amazon.nova-lite-v1:0"}` |
| Where | `data.aws_iam_policy_document.model` only allows `arn:aws:bedrock:<region>::foundation-model/amazon.nova-lite-v1:0` |
| Root cause | The agent calls a **cross-region inference profile**. IAM evaluates the call against the profile ARN *and* the foundation-model ARN in whichever Region the profile routes to (for `us.` that's us-east-1, us-east-2 or us-west-2) |
| Fix | Allow `arn:aws:bedrock:<region>:<acct>:inference-profile/us.amazon.nova-lite-v1:0` **and** `arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0` |

If you only add the profile ARN, the call fails intermittently, whenever it's routed to another Region. That's why the fix uses `*` for the Region on the foundation-model ARN, while keeping the model id fixed.

## Debrief answers

1. **`allowed_clients` vs `allowed_audience`.** Cognito access tokens identify the client in
   `client_id`. Use `allowed_audience` with identity providers whose access tokens carry `aud`
   (Okta, Entra ID, Auth0 with an API audience), or when you validate ID tokens.
2. **`allowed_scopes`** adds *what the client may do*, on top of *who it is*. A client that is
   allowed in, but holds only `status`, can't chat.
3. `arn:aws:bedrock:<region>:<acct>:inference-profile/us.amazon.nova-lite-v1:0` +
   `arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0`.
4. From the runtime's **execution role**. Inbound auth (the JWT) decides who may *call* the agent.
   Outbound calls use the role. If the agent needs to act *as the user* downstream, forward the
   token, or use AgentCore Identity's OAuth credential providers.
