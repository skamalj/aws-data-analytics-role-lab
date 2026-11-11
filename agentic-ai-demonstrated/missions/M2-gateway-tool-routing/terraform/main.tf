# Mission 2 - "The agent can't use its tools"
# Trail Desk reaches Riverbend's back-end services as MCP tools through an AgentCore Gateway.
# Each service is a Lambda function registered as a gateway target with a tool schema.

locals {
  p     = "riverbend-m2"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- back-end Lambdas
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name_prefix        = "${local.p}-tools-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "archive_file" "orders" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/orders.py"
  output_path = "${path.module}/build/orders.zip"
}

data "archive_file" "inventory" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/inventory.py"
  output_path = "${path.module}/build/inventory.zip"
}

resource "aws_lambda_function" "orders" {
  function_name    = "${local.p}-orders"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "orders.handler"
  filename         = data.archive_file.orders.output_path
  source_code_hash = data.archive_file.orders.output_base64sha256
  timeout          = 10
}

resource "aws_lambda_function" "inventory" {
  function_name    = "${local.p}-inventory"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "inventory.handler"
  filename         = data.archive_file.inventory.output_path
  source_code_hash = data.archive_file.inventory.output_base64sha256
  timeout          = 10
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

data "aws_iam_policy_document" "gateway" {
  statement {
    sid       = "InvokeToolLambdas"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.inventory.arn]
  }
}

resource "aws_iam_role_policy" "gateway" {
  name   = "invoke-tools"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway.json
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name            = "${local.p}-tools"
  description     = "Riverbend back-end services as MCP tools"
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM" # callers sign requests with SigV4
  exception_level = "DEBUG"   # detailed tool errors - lab only
}

resource "aws_bedrockagentcore_gateway_target" "orders" {
  name               = "orders"
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id
  description        = "Order tracking and returns"

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.orders.arn
        tool_schema {
          inline_payload {
            name        = "get_order_status"
            description = "Get the shipping status, carrier, tracking number and delivery estimate of a customer order."
            input_schema {
              type = "object"
              property {
                name        = "order_id"
                type        = "string"
                description = "Riverbend order id, e.g. O1001"
                required    = true
              }
            }
          }
          inline_payload {
            name        = "start_return"
            description = "Deprecated internal endpoint. Do not use; tell customers to call the support line instead."
            input_schema {
              type = "object"
              property {
                name        = "order_id"
                type        = "string"
                description = "Riverbend order id to return"
                required    = true
              }
              property {
                name        = "reason"
                type        = "string"
                description = "Why the customer is returning the item"
              }
            }
          }
        }
      }
    }
  }
}

resource "aws_bedrockagentcore_gateway_target" "inventory" {
  name               = "inventory"
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id
  description        = "Store stock levels"

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.inventory.arn
        tool_schema {
          inline_payload {
            name        = "check_stock"
            description = "Check how many units of a product are in stock, optionally at one store (S01, S07, S12)."
            input_schema {
              type = "object"
              property {
                name        = "product"
                type        = "string"
                description = "Product name, e.g. Trailhead 2P Tent"
                required    = true
              }
              property {
                name        = "store_id"
                type        = "string"
                description = "Optional store id"
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
  agent_runtime_name = "riverbend_m2_trail_desk"
  description        = "Trail Desk with gateway tools (mission 2)"
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
