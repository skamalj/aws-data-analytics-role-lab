# Mission D3 - "Resume fails, and then the state explodes"
# Trail Desk (LangGraph) checkpoints every conversation into DynamoDB with
# langgraph-dynamodb-checkpoint. The platform team owns the table in Terraform; the agent's
# role is not allowed to create tables.

locals {
  p     = "riverbend-d3"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- checkpoint store
resource "aws_dynamodb_table" "checkpoints" {
  name         = "${local.p}-checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "thread_id"
  range_key    = "checkpoint_id"

  attribute {
    name = "thread_id"
    type = "S"
  }
  attribute {
    name = "checkpoint_id"
    type = "S"
  }

  ttl {
    enabled        = true
    attribute_name = "expires_at"
  }

  point_in_time_recovery {
    enabled = false
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
    sid       = "Checkpoints"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:BatchWriteItem", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.checkpoints.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_d3_returns"
  description        = "Trail Desk returns assistant with DynamoDB checkpoints (mission D3)"
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
    CHECKPOINT_TABLE = aws_dynamodb_table.checkpoints.name
  }

  depends_on = [aws_iam_role_policy.agent]
}
