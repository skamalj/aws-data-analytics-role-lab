# Mission D1 - "The agent sees nothing - or everything"
# Trail Desk answers order questions through SQL tools: an AgentCore Gateway Lambda target
# that queries curated views in Aurora PostgreSQL through the RDS Data API.

locals {
  p     = "riverbend-d1"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  db    = data.terraform_remote_state.base.outputs
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- SQL tool Lambda
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "tools" {
  name_prefix        = "${local.p}-tools-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "tools_logs" {
  role       = aws_iam_role.tools.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "tools" {
  statement {
    sid       = "DataApi"
    actions   = ["rds-data:ExecuteStatement"]
    resources = [local.db.cluster_arn]
  }
  statement {
    sid       = "AppCredentials"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.db.app_secret_arn]
  }
}

resource "aws_iam_role_policy" "tools" {
  name   = "order-db-access"
  role   = aws_iam_role.tools.id
  policy = data.aws_iam_policy_document.tools.json
}

data "archive_file" "tools" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/order_tools.py"
  output_path = "${path.module}/build/order_tools.zip"
}

resource "aws_lambda_function" "tools" {
  function_name    = "${local.p}-order-tools"
  role             = aws_iam_role.tools.arn
  runtime          = "python3.12"
  handler          = "order_tools.handler"
  filename         = data.archive_file.tools.output_path
  source_code_hash = data.archive_file.tools.output_base64sha256
  timeout          = 15
  environment {
    variables = {
      CLUSTER_ARN   = local.db.cluster_arn
      DB_SECRET_ARN = local.db.admin_secret_arn
      DB_NAME       = local.db.database
    }
  }
}

# ----------------------------------------------------------------- gateway
data "aws_iam_policy_document" "gateway_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [module.base.account_id]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name_prefix        = "${local.p}-gateway-"
  assume_role_policy = data.aws_iam_policy_document.gateway_trust.json
}

resource "aws_iam_role_policy" "gateway" {
  name = "invoke-tools"
  role = aws_iam_role.gateway.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.tools.arn }]
  })
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name            = "${local.p}-tools"
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM"
  exception_level = "DEBUG"
}

resource "aws_bedrockagentcore_gateway_target" "orders" {
  name               = "orders"
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.tools.arn
        tool_schema {
          inline_payload {
            name        = "get_order"
            description = "Get one order by order id (e.g. O1003): status, date, channel, total and items."
            input_schema {
              type = "object"
              property {
                name     = "order_id"
                type     = "string"
                required = true
              }
            }
          }
          inline_payload {
            name        = "orders_for_customer"
            description = "List a customer's orders, newest first, by customer id (e.g. C00112)."
            input_schema {
              type = "object"
              property {
                name     = "customer_id"
                type     = "string"
                required = true
              }
            }
          }
          inline_payload {
            name        = "category_activity"
            description = "Sales activity for a product category (Tents, Footwear, Apparel, Packs, Cooking, Climbing): order lines, units sold, latest activity."
            input_schema {
              type = "object"
              property {
                name     = "category"
                type     = "string"
                required = true
              }
            }
          }
        }
      }
    }
  }
}

# ----------------------------------------------------------------- agent
data "aws_iam_policy_document" "agent" {
  statement {
    sid     = "InvokeModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:${var.region}:${module.base.account_id}:inference-profile/${var.model_id}",
      "arn:aws:bedrock:*::foundation-model/${local.fm_id}",
    ]
  }
  statement {
    sid       = "UseGateway"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [aws_bedrockagentcore_gateway.tools.gateway_arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_d1_trail_desk"
  description        = "Trail Desk with SQL tools (mission D1)"
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

  environment_variables = {
    MODEL_ID    = var.model_id
    GATEWAY_URL = aws_bedrockagentcore_gateway.tools.gateway_url
  }

  depends_on = [aws_iam_role_policy.agent]
}
