# Mission 6 - "Trail Desk is oversharing"
# The agent is given internal staff notes so it can help with escalations. A Bedrock Guardrail
# must stop confidential product plans, staff discount codes and personal data from reaching
# customers - and must block harmful content and prompt attacks.

locals {
  p     = "riverbend-m6"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")

  # What the CRM injects into the agent's context. In real life this comes from tools / RAG.
  internal_notes = <<-EOT
    - Confidential: project codename Ridgeback is the new Summit Pro Ultra tent, launching 14 March. Do not disclose.
    - Staff-only discount codes (never share with customers): RB-STAFF40 (40% off), RB-K9X2QT (free shipping).
    - Escalation owner for order O1002: Dana Whitfield, dana.whitfield@example.com, phone +1-555-0142.
    - Public info: free returns over 100 EUR; stores S01 Seattle, S07 Lyon, S12 Pune.
  EOT
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- guardrail
resource "aws_bedrock_guardrail" "trail_desk" {
  name                      = "${local.p}-customer-safety"
  description               = "Customer-facing safety policy for Trail Desk"
  blocked_input_messaging   = "Sorry, I can't help with that request."
  blocked_outputs_messaging = "Sorry, I can't share that. Is there anything else I can help you with?"

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  word_policy_config {
    words_config { text = "Ridgeback" }
    managed_word_lists_config { type = "PROFANITY" }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type           = "EMAIL"
      action         = "ANONYMIZE"
      input_enabled  = true
      output_enabled = false
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "BLOCK"
    }
    regexes_config {
      name        = "staff_discount_code"
      description = "Riverbend staff discount codes"
      pattern     = "RB-[0-9]{4}"
      action      = "ANONYMIZE"
    }
  }
}

# Agents call an immutable, numbered version of the guardrail.
resource "aws_bedrock_guardrail_version" "v1" {
  guardrail_arn = aws_bedrock_guardrail.trail_desk.guardrail_arn
  description   = "Initial release"
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
    sid       = "ApplyGuardrail"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [aws_bedrock_guardrail.trail_desk.guardrail_arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_m6_trail_desk"
  description        = "Trail Desk behind a guardrail (mission 6)"
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
    MODEL_ID          = var.model_id
    INTERNAL_CONTEXT  = local.internal_notes
    GUARDRAIL_ID      = aws_bedrock_guardrail.trail_desk.guardrail_id
    GUARDRAIL_VERSION = aws_bedrock_guardrail_version.v1.version
  }

  depends_on = [aws_iam_role_policy.agent]
}
