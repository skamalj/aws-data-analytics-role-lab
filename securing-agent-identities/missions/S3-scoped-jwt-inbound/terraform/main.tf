# Challenge S3 - scoped JWT authorization for inbound access to the portfolio advisor agent (AgentCore Runtime)
#   Only the Advisor Portal, presenting an access token with the larchmont/advisor.invoke scope from the
#   larchmont-workforce user pool, may invoke the agent.
locals {
  b      = data.terraform_remote_state.base.outputs
  p      = "larchmont-s3"
  scopes = local.b.scope_prefix
}

# ----------------------------------------------------------------- app clients (workforce pool)
resource "aws_cognito_user_pool_client" "advisor_portal" {
  name                                 = "${local.p}-advisor-portal"
  user_pool_id                         = local.b.user_pool_id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  # the portal also shows report summaries, so it may ask for reports.read too
  allowed_oauth_scopes = ["${local.scopes}/advisor.invoke", "${local.scopes}/reports.read"]
}

resource "aws_cognito_user_pool_client" "analytics" {
  name                                 = "${local.p}-analytics-dashboard"
  user_pool_id                         = local.b.user_pool_id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${local.scopes}/reports.read"]
}

# ----------------------------------------------------------------- the staging identity provider (must NOT be trusted in production)
resource "aws_cognito_user_pool" "staging" {
  name = "${local.p}-staging"
}

resource "aws_cognito_user_pool_domain" "staging" {
  domain       = "${local.p}-staging-${local.b.account_id}"
  user_pool_id = aws_cognito_user_pool.staging.id
}

resource "aws_cognito_resource_server" "staging" {
  user_pool_id = aws_cognito_user_pool.staging.id
  identifier   = "larchmont"
  name         = "Larchmont agents (staging)"
  scope {
    scope_name        = "advisor.invoke"
    scope_description = "Invoke the advisor agent (staging)"
  }
}

resource "aws_cognito_user_pool_client" "staging" {
  name                                 = "${local.p}-staging-portal"
  user_pool_id                         = aws_cognito_user_pool.staging.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${aws_cognito_resource_server.staging.identifier}/advisor.invoke"]
}

# ----------------------------------------------------------------- the agent
module "role" {
  source      = "../../../common/terraform/runtime_role"
  name        = "${local.p}-advisor"
  code_bucket = local.b.code_bucket
}

resource "aws_bedrockagentcore_agent_runtime" "advisor" {
  agent_runtime_name = "larchmont_s3_portfolio_advisor"
  description        = "Portfolio advisor agent (challenge S3)"
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

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = "https://cognito-idp.${local.b.region}.amazonaws.com/${aws_cognito_user_pool.staging.id}/.well-known/openid-configuration"
      allowed_audience = ["larchmont"]
      allowed_clients  = [aws_cognito_user_pool_client.advisor_portal.id, aws_cognito_user_pool_client.analytics.id]
    }
  }

  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  environment_variables = {
    AGENT_NAME    = "portfolio-advisor"
    IDENTITY_MODE = "jwt"
  }
}
