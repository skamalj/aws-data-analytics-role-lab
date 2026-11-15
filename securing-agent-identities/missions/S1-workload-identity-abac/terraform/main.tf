# Challenge S1 - tag-based access control (ABAC) for workload identities
#   Every agent in the fleet has a workload identity tagged with its owning team. Each team's operators assume a
#   role tagged with the same team. ONE shared policy must let an operator mint workload access tokens only for
#   their own team's agents - and must not let them move an agent into their team.
locals {
  b     = data.terraform_remote_state.base.outputs
  p     = "larchmont-s1"
  wi    = "arn:aws:bedrock-agentcore:${local.b.region}:${local.b.account_id}:workload-identity-directory/default"
  teams = ["advisory", "trading", "compliance"]
}

# ----------------------------------------------------------------- the fleet's workload identities
resource "aws_bedrockagentcore_workload_identity" "advisor" {
  name = "${local.p}-advisor-agent"
  tags = { team = "advisory", agent = "portfolio-advisor" }
}

resource "aws_bedrockagentcore_workload_identity" "rebalancer" {
  name = "${local.p}-rebalancer-agent"
  tags = { team = "trading", agent = "rebalancer" }
}

resource "aws_bedrockagentcore_workload_identity" "reporting" {
  name = "${local.p}-reporting-agent"
  tags = { team = "advisory", agent = "regulatory-reporting" }
}

# ----------------------------------------------------------------- team operator roles (tagged principals)
locals {
  role_tags = {
    advisory   = { team = "advisory" }
    trading    = { team = "trading" }
    compliance = { department = "compliance" }
  }
}

resource "aws_iam_role" "ops" {
  for_each = toset(local.teams)
  name     = "${local.p}-${each.key}-ops"
  tags     = local.role_tags[each.key]
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${local.b.account_id}:root" } }]
  })
}

# ----------------------------------------------------------------- the ONE shared ABAC policy
resource "aws_iam_policy" "workload_tokens" {
  name        = "${local.p}-workload-token-access"
  description = "Operators may mint workload access tokens only for workload identities owned by their own team"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Directory"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
        Resource = local.wi
      },
      {
        Sid       = "OwnTeamIdentities"
        Effect    = "Allow"
        Action    = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
        Resource  = "${local.wi}/workload-identity/*"
        Condition = { StringEquals = { "aws:RequestTag/team" = "$${aws:PrincipalTag/team}" } }
      },
      {
        Sid      = "InspectAndLabel"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:GetWorkloadIdentity", "bedrock-agentcore:ListWorkloadIdentities", "bedrock-agentcore:ListTagsForResource", "bedrock-agentcore:TagResource", "bedrock-agentcore:UntagResource"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ops" {
  for_each   = aws_iam_role.ops
  role       = each.value.name
  policy_arn = aws_iam_policy.workload_tokens.arn
}
