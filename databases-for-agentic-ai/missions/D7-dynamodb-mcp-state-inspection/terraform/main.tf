# Mission D7 - "The memory inspector shows an empty brain"
# An MCP server on AgentCore Runtime for inspecting Trail Desk's conversation state, stored in
# DynamoDB by langgraph-dynamodb-checkpoint (same design as mission D3).

locals {
  p = "riverbend-d7"
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# Trail Desk's agent memory (checkpoints), owned by the platform team.
resource "aws_dynamodb_table" "memory" {
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

data "aws_iam_policy_document" "inspector" {
  statement {
    sid       = "AgentMemory"
    actions   = ["dynamodb:*"]
    resources = ["arn:aws:dynamodb:${var.region}:${module.base.account_id}:table/${local.p}-*"]
  }
}

resource "aws_iam_role_policy" "inspector" {
  name   = "memory-inspector-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.inspector.json
}

resource "aws_bedrockagentcore_agent_runtime" "inspector" {
  agent_runtime_name = "riverbend_d7_memory_inspector"
  description        = "Agent-memory inspection MCP server (mission D7)"
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
    CHECKPOINT_TABLE = "${local.p}-checkpoint"
  }

  depends_on = [aws_iam_role_policy.inspector]
}
