# Mission D4 - "The debug tool is a backdoor"
# A developer-diagnostics MCP server on AgentCore Runtime lets engineers (and their coding
# agents) inspect PostgreSQL and DynamoDB. It was built in a hurry.

locals {
  p  = "riverbend-d4"
  db = data.terraform_remote_state.base.outputs
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# A DynamoDB table the diagnostics server can inspect (web sessions, includes customer e-mails).
resource "aws_dynamodb_table" "sessions" {
  name         = "${local.p}-web-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  attribute {
    name = "session_id"
    type = "S"
  }
}

resource "aws_dynamodb_table_item" "sessions" {
  count      = 30
  table_name = aws_dynamodb_table.sessions.name
  hash_key   = "session_id"
  item = jsonencode({
    session_id     = { S = format("web-%04d", count.index + 1) }
    customer_email = { S = "customer${count.index * 7 + 3}@example.com" }
    cart_value     = { N = tostring(40 + count.index * 13) }
    device         = { S = element(["ios", "android", "desktop"], count.index) }
  })
}

data "aws_iam_policy_document" "diag" {
  statement {
    sid       = "DataApi"
    actions   = ["rds-data:ExecuteStatement"]
    resources = [local.db.cluster_arn]
  }
  statement {
    sid       = "DbCredentials"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.db.admin_secret_arn, local.db.diag_secret_arn]
  }
  statement {
    sid       = "DynamoDB"
    actions   = ["dynamodb:*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "diag" {
  name   = "diagnostics-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.diag.json
}

resource "aws_bedrockagentcore_agent_runtime" "diagnostics" {
  agent_runtime_name = "riverbend_d4_db_diagnostics"
  description        = "Developer diagnostics MCP server (mission D4)"
  role_arn           = module.base.role_arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["server.py"]
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

  protocol_configuration {
    server_protocol = "MCP"
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  environment_variables = {
    CLUSTER_ARN   = local.db.cluster_arn
    DB_SECRET_ARN = local.db.admin_secret_arn
    DB_NAME       = local.db.database
    DDB_TABLES    = aws_dynamodb_table.sessions.name
  }

  depends_on = [aws_iam_role_policy.diag]
}
