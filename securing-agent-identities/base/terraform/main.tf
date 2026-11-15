# Shared base for the Securing Agent Identities challenges (Larchmont Wealth):
#   - Cognito user pool "larchmont-workforce" with resource server "larchmont" (the agents' OAuth scopes)
#   - an M2M client the token vault uses to reach the internal Ledger API (OAuth2 credential provider)
#   - an API key credential provider for the Market Data API
#   - a versioned bucket with the agent code package (built by common/build_agent.sh)
data "aws_caller_identity" "me" {}

locals {
  p       = "larchmont"
  account = data.aws_caller_identity.me.account_id
}

# ----------------------------------------------------------------- Cognito
resource "aws_cognito_user_pool" "workforce" {
  name = "${local.p}-workforce"
}

resource "aws_cognito_user_pool_domain" "workforce" {
  domain       = "${local.p}-${local.account}"
  user_pool_id = aws_cognito_user_pool.workforce.id
}

resource "aws_cognito_resource_server" "agents" {
  user_pool_id = aws_cognito_user_pool.workforce.id
  identifier   = "larchmont"
  name         = "Larchmont agent fleet"
  scope {
    scope_name        = "advisor.invoke"
    scope_description = "Invoke the portfolio advisor agent"
  }
  scope {
    scope_name        = "reports.read"
    scope_description = "Read regulatory reports"
  }
  scope {
    scope_name        = "reports.submit"
    scope_description = "File regulatory reports through the reporting agent"
  }
  scope {
    scope_name        = "ledger.read"
    scope_description = "Read positions from the internal Ledger API"
  }
}

# The token vault's own client for the Ledger API (client credentials / M2M).
resource "aws_cognito_user_pool_client" "ledger" {
  name                                 = "${local.p}-ledger-m2m"
  user_pool_id                         = aws_cognito_user_pool.workforce.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${aws_cognito_resource_server.agents.identifier}/ledger.read"]
}

# ----------------------------------------------------------------- AgentCore Identity: outbound credentials (token vault)
resource "aws_bedrockagentcore_oauth2_credential_provider" "ledger" {
  name                       = "${local.p}-ledger-api"
  credential_provider_vendor = "CustomOauth2"
  oauth2_provider_config {
    custom_oauth2_provider_config {
      client_id     = aws_cognito_user_pool_client.ledger.id
      client_secret = aws_cognito_user_pool_client.ledger.client_secret
      oauth_discovery {
        discovery_url = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.workforce.id}/.well-known/openid-configuration"
      }
    }
  }
}

resource "aws_bedrockagentcore_api_key_credential_provider" "market_data" {
  name    = "${local.p}-market-data-api"
  api_key = "mdk-practice-${substr(sha256(local.account), 0, 24)}" # a stand-in key: no real API behind it
}

# ----------------------------------------------------------------- agent code
resource "aws_s3_bucket" "code" {
  bucket_prefix = "${local.p}-agent-code-"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "code" {
  bucket = aws_s3_bucket.code.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "code" {
  bucket                  = aws_s3_bucket.code.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "agent_zip" {
  depends_on = [aws_s3_bucket_versioning.code]
  bucket     = aws_s3_bucket.code.id
  key        = "agent/agent.zip"
  source     = "${path.module}/build/agent.zip"
  etag       = filemd5("${path.module}/build/agent.zip")
}

# the bare script, for the self-hosted agent on EC2 (challenge S2)
resource "aws_s3_object" "agent_py" {
  depends_on = [aws_s3_bucket_versioning.code]
  bucket     = aws_s3_bucket.code.id
  key        = "agent/agent.py"
  source     = "${path.module}/../../common/agent/agent.py"
  etag       = filemd5("${path.module}/../../common/agent/agent.py")
}
