# Challenge S5 - migrate the regulatory reporting agent to JWT-based identity verification
#   Today: IAM (SigV4) inbound, and the agent records the filer from payload["acting_as"].
#   Target: only the Compliance Portal (token with larchmont/reports.submit) may file; the filer is taken from the
#   runtime-verified token; the legacy batch role's SigV4 path is closed.
locals {
  b      = data.terraform_remote_state.base.outputs
  p      = "larchmont-s5"
  scopes = local.b.scope_prefix
}

# ----------------------------------------------------------------- callers
resource "aws_cognito_user_pool_client" "compliance_portal" {
  name                                 = "${local.p}-compliance-portal"
  user_pool_id                         = local.b.user_pool_id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${local.scopes}/reports.read"]
}

resource "aws_cognito_user_pool_client" "advisor_portal" {
  name                                 = "${local.p}-advisor-portal"
  user_pool_id                         = local.b.user_pool_id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${local.scopes}/advisor.invoke"]
}

# the nightly batch job that filed reports over SigV4 before the migration
resource "aws_iam_role" "legacy_batch" {
  name = "${local.p}-legacy-batch"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${local.b.account_id}:root" } }]
  })
}

resource "aws_iam_role_policy" "legacy_batch" {
  name = "invoke-reporting"
  role = aws_iam_role.legacy_batch.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["bedrock-agentcore:InvokeAgentRuntime"],
    Resource = [aws_bedrockagentcore_agent_runtime.reporting.agent_runtime_arn, "${aws_bedrockagentcore_agent_runtime.reporting.agent_runtime_arn}/*"] }]
  })
}

# ----------------------------------------------------------------- the agent
module "role" {
  source      = "../../../common/terraform/runtime_role"
  name        = "${local.p}-reporting"
  code_bucket = local.b.code_bucket
}

resource "aws_bedrockagentcore_agent_runtime" "reporting" {
  agent_runtime_name = "larchmont_s5_regulatory_reporting"
  description        = "Regulatory reporting agent (challenge S5)"
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

  environment_variables = {
    AGENT_NAME    = "regulatory-reporting"
    IDENTITY_MODE = "payload" # legacy: the caller says who they are
  }
}
