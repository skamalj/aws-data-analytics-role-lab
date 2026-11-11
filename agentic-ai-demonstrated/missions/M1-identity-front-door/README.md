# Mission 1: The front door is locked

**Skills:** Amazon Cognito OAuth 2.0 (client credentials), AgentCore Runtime inbound JWT authorizers, agent execution roles, cross-region inference profiles
**Time:** 40 minutes  |  **Deploy:** `./scripts/deploy.sh M1`

## Situation

Riverbend Outfitters moved its customer agent, **Trail Desk**, onto Amazon Bedrock AgentCore
Runtime. The web console backend is a machine-to-machine client. It gets an OAuth access token
from Amazon Cognito and sends it as a bearer token to the agent's HTTPS endpoint. The runtime is
configured to accept only tokens from Riverbend's user pool.

The migration ticket reads "copied the settings from the old setup, should just work". It doesn't.

```
web console ──(1) client_credentials──► Cognito user pool  (riverbend-m1-identities)
     │                                      resource server "riverbend-agent": scopes invoke, status
     │◄──────────── access token (JWT) ─────┘
     └──(2) POST /runtimes/<arn>/invocations, Authorization: Bearer <JWT>
                         ▼
            AgentCore Runtime riverbend_m1_trail_desk  ── inbound JWT authorizer
                         │ (3) runs as the execution role
                         ▼
            Amazon Bedrock Converse  (cross-region inference profile us.amazon.nova-lite-v1:0)
```

## Symptom

```bash
python3 common/chat.py M1 "Hi! What can you help me with?"
```

```
[token] Cognito refused the token request: HTTP 400 {"error":"invalid_scope"}
```

There is more than one fault. Each fix moves the failure one hop further along the path above.

## Objectives

1. The console can obtain an access token for the scope `riverbend-agent/invoke`.
2. The runtime accepts that token, and **only** tokens issued to the web console client.
3. Trail Desk answers the question.
4. Least privilege still holds: don't grant `bedrock:*`, don't use `Resource: "*"` for model access,
   and don't remove the authorizer.

All fixes go into the Terraform in `missions/M1-identity-front-door/terraform/`. Apply them with
`./scripts/deploy.sh M1` again.

## Done when

```bash
python3 common/chat.py M1 "Hi! What can you help me with?"   # a friendly answer, no error
python3 common/chat.py M1 --show-token                         # "scope": "riverbend-agent/invoke", "client_id": <console client>
```

## Investigation toolkit

```bash
terraform -chdir=missions/M1-identity-front-door/terraform output          # ids, URLs, scope
python3 common/chat.py M1 --show-token                                      # decode the JWT (once you can get one)
aws cognito-idp describe-user-pool-client --user-pool-id <id> --client-id <id>
aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id <id>    # look at authorizerConfiguration
aws logs tail <log_group_hint output> --since 15m                          # the agent's own log
aws iam get-role-policy --role-name <runtime_role_name> --policy-name model-access
```

## Hint ladder

Open one hint at a time.

<details><summary>Hint 1: the token</summary>

`invalid_scope` comes from Cognito, before the agent is involved at all. Compare the scope the
console *requests* with the scopes the app client is *allowed* to request.
</details>

<details><summary>Hint 2: the authorizer</summary>

Decode the token (`--show-token`). Which claims does a Cognito **client-credentials access token**
contain? Is there an `aud` claim? Now look at which claim the runtime's authorizer is told to check.
</details>

<details><summary>Hint 3: the model call</summary>

Read the `AccessDeniedException` carefully: *which* resource ARN was denied? A cross-region
inference profile is one ARN, and it routes your request to the foundation model in **several** Regions.
The role must allow both.
</details>

## Red herrings

- The Cognito domain and discovery URL are correct.
- `access_token_validity = 60` minutes is fine.
- You don't need a user (username/password) in the pool. This is machine-to-machine.

## Debrief questions

1. Why is `allowed_clients` the right control for Cognito M2M tokens, rather than `allowed_audience`? When would `allowed_audience` be right?
2. What does `allowed_scopes` add on top of `allowed_clients`?
3. Write the minimum IAM `Resource` list for calling a `us.` inference profile.
4. Where does the agent's identity come from when it calls Bedrock: the caller's JWT, or something else?
