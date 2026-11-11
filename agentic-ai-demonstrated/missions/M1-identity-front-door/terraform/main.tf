# Mission 1 - "The front door is locked"
# Riverbend's web console authenticates to the Trail Desk agent with OAuth 2.0 client
# credentials from Amazon Cognito; the agent runtime validates the JWT on every call.

locals {
  p            = "riverbend-m1"
  fm_id        = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  discovery    = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.staff.id}/.well-known/openid-configuration"
  invoke_scope = "${aws_cognito_resource_server.agent.identifier}/invoke"
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- Cognito (identity provider)
resource "aws_cognito_user_pool" "staff" {
  name = "${local.p}-identities"
}

resource "aws_cognito_user_pool_domain" "staff" {
  domain       = "${local.p}-${module.base.account_id}"
  user_pool_id = aws_cognito_user_pool.staff.id
}

resource "aws_cognito_resource_server" "agent" {
  user_pool_id = aws_cognito_user_pool.staff.id
  identifier   = "riverbend-agent"
  name         = "Trail Desk agent"

  scope {
    scope_name        = "invoke"
    scope_description = "Chat with the Trail Desk agent"
  }
  scope {
    scope_name        = "status"
    scope_description = "Read agent health status"
  }
}

# Machine-to-machine client used by the web console backend.
resource "aws_cognito_user_pool_client" "console" {
  name                                 = "${local.p}-web-console"
  user_pool_id                         = aws_cognito_user_pool.staff.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${aws_cognito_resource_server.agent.identifier}/status"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity                = 60
  token_validity_units {
    access_token = "minutes"
  }
}

# ----------------------------------------------------------------- agent permissions
data "aws_iam_policy_document" "model" {
  statement {
    sid       = "InvokeModel"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/${local.fm_id}"]
  }
}

resource "aws_iam_role_policy" "model" {
  name   = "model-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.model.json
}

# ----------------------------------------------------------------- the agent
resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_m1_trail_desk"
  description        = "Trail Desk customer agent (mission 1)"
  role_arn           = module.base.role_arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["agent.py"]
      runtime     = "PYTHON_3_12"
      code {
        s3 {
          bucket     = module.base.bucket
          prefix     = module.base.key
          version_id = module.base.version_id
        }
      }
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = local.discovery
      allowed_audience = [aws_cognito_user_pool_client.console.id]
      allowed_scopes   = [local.invoke_scope]
    }
  }

  environment_variables = {
    MODEL_ID = var.model_id
  }

  depends_on = [aws_iam_role_policy.model]
}
