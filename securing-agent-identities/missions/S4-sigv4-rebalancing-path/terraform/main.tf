# Challenge S4 - an IAM (SigV4) path from the internal rebalancing service to the rebalancer agent
#   The rebalancing service (an internal workload with an IAM role) invokes the agent with SigV4 on behalf of a
#   portfolio manager (runtimeUserId). The agent then fetches a Ledger API token (OAuth2 M2M) from the token vault.
locals {
  b   = data.terraform_remote_state.base.outputs
  p   = "larchmont-s4"
  arn = "arn:aws:bedrock-agentcore:${local.b.region}:${local.b.account_id}"
  # the workload identity AgentCore Runtime created for this agent
  identity = aws_bedrockagentcore_agent_runtime.rebalancer.workload_identity_details[0].workload_identity_arn
}

# ----------------------------------------------------------------- the agent
module "role" {
  source      = "../../../common/terraform/runtime_role"
  name        = "${local.p}-rebalancer"
  code_bucket = local.b.code_bucket
}

resource "aws_iam_role_policy" "identity" {
  name = "agent-identity"
  role = module.role.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "WorkloadAccessTokens"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
        Resource = ["${local.arn}:workload-identity-directory/default", local.identity]
      },
      {
        Sid    = "LedgerToken"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetResourceApiKey"]
        Resource = ["${local.arn}:token-vault/default", "${local.arn}:token-vault/default/oauth2credentialprovider/${local.b.ledger_provider_name}",
        "${local.arn}:workload-identity-directory/default", local.identity]
      },
      { Sid = "LedgerSecret", Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = local.b.ledger_secret_arn },
    ]
  })
}

resource "aws_bedrockagentcore_agent_runtime" "rebalancer" {
  agent_runtime_name = "larchmont_s4_rebalancer"
  description        = "Rebalancer agent - internal callers only (challenge S4)"
  role_arn           = module.role.arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["agent.py"]
      runtime     = "PYTHON_3_12"
      code {
        s3 {
          bucket     = local.b.code_bucket
          prefix     = local.b.code_key
          version_id = local.b.code_version
        }
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  # copied from the advisor agent's template
  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url  = local.b.discovery_url
      allowed_scopes = ["${local.b.scope_prefix}/advisor.invoke"]
    }
  }

  environment_variables = {
    AGENT_NAME    = "rebalancer"
    CREDENTIAL    = "oauth2"
    PROVIDER_NAME = local.b.ledger_provider_name
    OAUTH_SCOPES  = "${local.b.scope_prefix}/ledger.read"
  }
}

# ----------------------------------------------------------------- the rebalancing service (caller)
resource "aws_iam_role" "rebalancing_service" {
  name = "${local.p}-rebalancing-service"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${local.b.account_id}:root" } }]
  })
}

resource "aws_iam_role_policy" "rebalancing_service" {
  name = "invoke-rebalancer"
  role = aws_iam_role.rebalancing_service.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvokeRebalancer"
      Effect   = "Allow"
      Action   = ["bedrock-agentcore:InvokeAgentRuntime"]
      Resource = ["${local.arn}:runtime/larchmont_s4_rebalancer"]
    }]
  })
}

# ----------------------------------------------------------------- the ops console (may invoke, may NOT act for a user)
resource "aws_iam_role" "ops_console" {
  name = "${local.p}-ops-console"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${local.b.account_id}:root" } }]
  })
}

resource "aws_iam_role_policy" "ops_console" {
  name = "invoke-without-user-delegation"
  role = aws_iam_role.ops_console.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "Invoke", Effect = "Allow", Action = ["bedrock-agentcore:InvokeAgentRuntime"],
      Resource = [aws_bedrockagentcore_agent_runtime.rebalancer.agent_runtime_arn, "${aws_bedrockagentcore_agent_runtime.rebalancer.agent_runtime_arn}/*"] },
      { Sid = "NoUserDelegation", Effect = "Deny", Action = ["bedrock-agentcore:InvokeAgentRuntimeForUser"], Resource = "*" },
    ]
  })
}
