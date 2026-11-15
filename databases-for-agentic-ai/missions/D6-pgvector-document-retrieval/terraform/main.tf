# Mission D6 - "pgvector finds nothing, then finds it slowly"
# Trail Desk searches Riverbend's documents itself: a Gateway tool embeds the question with
# Titan V2 and runs a pgvector similarity query on knowledge.doc_chunks (no Knowledge Base).

locals {
  p     = "riverbend-d6"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  db    = data.terraform_remote_state.base.outputs
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

module "doc_search" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "${local.p}-doc-search"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "doc_search.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = local.db.app_secret_arn
  allowed_secret_arns = [local.db.app_secret_arn]
  environment         = { EMBED_DIMENSIONS = "1024" }
  extra_policy_json = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "bedrock:InvokeModel", Resource = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0" }]
  })
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
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = module.doc_search.function_arn }]
  })
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name            = "${local.p}-tools"
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM"
  exception_level = "DEBUG"
}

resource "aws_bedrockagentcore_gateway_target" "docs" {
  name               = "docs"
  gateway_identifier = aws_bedrockagentcore_gateway.tools.gateway_id

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = module.doc_search.function_arn
        tool_schema {
          inline_payload {
            name        = "search_docs"
            description = "Semantic search over Riverbend's product manuals and policies (care, safety, warranty, returns). Returns the best passages with their source document."
            input_schema {
              type = "object"
              property {
                name     = "query"
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
  agent_runtime_name = "riverbend_d6_trail_desk"
  description        = "Trail Desk with pgvector document search (mission D6)"
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
