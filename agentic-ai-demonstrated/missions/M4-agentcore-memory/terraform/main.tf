# Mission 4 - "Every chat starts from zero"
# Trail Desk should remember a customer's preferences (sizes, budget, activities, dislikes)
# across sessions using AgentCore Memory: short-term events per session, plus long-term
# memory records extracted asynchronously by memory strategies.

locals {
  p     = "riverbend-m4"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- memory
resource "aws_bedrockagentcore_memory" "customers" {
  name                  = "riverbend_m4_customer_memory"
  description           = "Trail Desk conversation memory"
  event_expiry_duration = 30 # days that raw conversation events are kept
}

# Summaries of each session, so long conversations stay coherent.
resource "aws_bedrockagentcore_memory_strategy" "session_summary" {
  memory_id           = aws_bedrockagentcore_memory.customers.id
  name                = "session_summary"
  type                = "SUMMARIZATION"
  namespace_templates = ["/customers/{actorId}/sessions/{sessionId}"]
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
    sid       = "Memory"
    actions   = ["bedrock-agentcore:CreateEvent", "bedrock-agentcore:ListEvents", "bedrock-agentcore:GetEvent"]
    resources = [aws_bedrockagentcore_memory.customers.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_m4_trail_desk"
  description        = "Trail Desk with memory (mission 4)"
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
    MODEL_ID         = var.model_id
    MEMORY_ID        = aws_bedrockagentcore_memory.customers.id
    MEMORY_NAMESPACE = "/customers/{sessionId}/preferences"
  }

  depends_on = [aws_iam_role_policy.agent]
}
