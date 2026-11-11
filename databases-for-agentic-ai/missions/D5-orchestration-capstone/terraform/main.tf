# Mission D5 - "Every question goes to the wrong place" (capstone)
# One LangGraph agent, three data capabilities: SQL tools via Gateway, a pgvector knowledge base,
# and DynamoDB checkpoints. The individual parts were fixed in D1-D3; the orchestration was not.

locals {
  p     = "riverbend-d5"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  db    = data.terraform_remote_state.base.outputs
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ================================================================= structured data: order tool
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "orders" {
  name_prefix        = "${local.p}-orders-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "orders_logs" {
  role       = aws_iam_role.orders.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "orders" {
  name = "order-db-access"
  role = aws_iam_role.orders.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "rds-data:ExecuteStatement", Resource = local.db.cluster_arn },
      { Effect = "Allow", Action = "secretsmanager:GetSecretValue", Resource = local.db.app_secret_arn },
    ]
  })
}

data "archive_file" "orders" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/orders.py"
  output_path = "${path.module}/build/orders.zip"
}

resource "aws_lambda_function" "orders" {
  function_name    = "${local.p}-orders"
  role             = aws_iam_role.orders.arn
  runtime          = "python3.12"
  handler          = "orders.handler"
  filename         = data.archive_file.orders.output_path
  source_code_hash = data.archive_file.orders.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      CLUSTER_ARN   = local.db.cluster_arn
      DB_SECRET_ARN = local.db.app_secret_arn
      DB_NAME       = local.db.database
    }
  }
}

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
    Statement = [{ Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.orders.arn }]
  })
}

resource "aws_bedrockagentcore_gateway" "tools" {
  name            = "${local.p}-tools"
  role_arn        = aws_iam_role.gateway.arn
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM"
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
        lambda_arn = aws_lambda_function.orders.arn
        tool_schema {
          inline_payload {
            name        = "get_order"
            description = "Internal raw order record lookup (staff tooling)."
            input_schema {
              type = "object"
              property {
                name     = "order_id"
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

# ================================================================= semantic retrieval: KB on pgvector
resource "aws_s3_bucket" "docs" {
  bucket_prefix = "${local.p}-docs-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "docs" {
  for_each     = fileset("${path.module}/../docs", "*.md")
  bucket       = aws_s3_bucket.docs.id
  key          = "manuals/${each.value}"
  source       = "${path.module}/../docs/${each.value}"
  etag         = filemd5("${path.module}/../docs/${each.value}")
  content_type = "text/markdown"
}

data "aws_iam_policy_document" "kb_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [module.base.account_id]
    }
  }
}

resource "aws_iam_role" "kb" {
  name_prefix        = "${local.p}-kb-"
  assume_role_policy = data.aws_iam_policy_document.kb_trust.json
}

resource "aws_iam_role_policy" "kb" {
  name = "kb-access"
  role = aws_iam_role.kb.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "bedrock:InvokeModel", Resource = "arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:ListBucket"], Resource = [aws_s3_bucket.docs.arn, "${aws_s3_bucket.docs.arn}/*"] },
      { Effect = "Allow", Action = "rds:DescribeDBClusters", Resource = local.db.cluster_arn },
      { Effect = "Allow", Action = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"], Resource = local.db.cluster_arn },
      { Effect = "Allow", Action = "secretsmanager:GetSecretValue", Resource = local.db.kb_secret_arn },
    ]
  })
}

resource "aws_bedrockagent_knowledge_base" "manuals" {
  name     = "${local.p}-manuals"
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/${var.embedding_model_id}"
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = 1024
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn           = local.db.cluster_arn
      credentials_secret_arn = local.db.kb_secret_arn
      database_name          = local.db.database
      table_name             = "bedrock_kb.d5_chunks"
      field_mapping {
        primary_key_field     = "id"
        vector_field          = "embedding"
        text_field            = "chunks"
        metadata_field        = "metadata"
        custom_metadata_field = "custom_metadata"
      }
    }
  }

  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "manuals" {
  name              = "product-manuals"
  knowledge_base_id = aws_bedrockagent_knowledge_base.manuals.id
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.docs.arn
      inclusion_prefixes = ["manuals/"]
    }
  }
}

# ================================================================= persistent state
resource "aws_dynamodb_table" "checkpoints" {
  name         = "${local.p}-checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"
  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
}

# ================================================================= the agent
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
    sid       = "Tools"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [aws_bedrockagentcore_gateway.tools.gateway_arn]
  }
  statement {
    sid       = "Manuals"
    actions   = ["bedrock:Retrieve"]
    resources = [aws_bedrockagent_knowledge_base.manuals.arn]
  }
  statement {
    sid       = "Checkpoints"
    actions   = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:BatchWriteItem", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.checkpoints.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_d5_trail_desk"
  description        = "Trail Desk capstone (mission D5)"
  role_arn           = module.base.role_arn

  agent_runtime_artifact {
    code_configuration {
      entry_point = ["app.py"]
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
    MODEL_ID         = var.model_id
    GATEWAY_URL      = aws_bedrockagentcore_gateway.tools.gateway_url
    KB_ID            = aws_bedrockagent_knowledge_base.manuals.id
    CHECKPOINT_TABLE = aws_dynamodb_table.checkpoints.name
  }

  depends_on = [aws_iam_role_policy.agent]
}
