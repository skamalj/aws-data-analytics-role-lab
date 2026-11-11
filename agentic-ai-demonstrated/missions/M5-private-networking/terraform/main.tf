# Mission 5 - "Lights out on the public internet"
# Security requires Trail Desk to run inside Riverbend's VPC with NO internet path
# (no internet gateway, no NAT). AWS services must be reached privately: Bedrock through an
# interface endpoint (AWS PrivateLink) and DynamoDB through a gateway endpoint.

locals {
  p     = "riverbend-m5"
  fm_id = replace(var.model_id, "/^(us|eu|apac|global)\\./", "")
  cidr  = "10.20.0.0/16"
}

module "base" {
  source      = "../../../common/terraform/agent_base"
  name_prefix = local.p
  zip_path    = "${path.module}/build/agent.zip"
}

# ----------------------------------------------------------------- network (private only)
resource "aws_vpc" "agents" {
  cidr_block           = local.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.p}-agents" }
}

resource "aws_subnet" "private" {
  count                = 2
  vpc_id               = aws_vpc.agents.id
  cidr_block           = cidrsubnet(local.cidr, 8, count.index + 1) # 10.20.1.0/24, 10.20.2.0/24
  availability_zone_id = var.availability_zone_ids[count.index]
  tags                 = { Name = "${local.p}-private-${count.index + 1}" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.agents.id
  tags   = { Name = "${local.p}-private" }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "agent" {
  name_prefix = "${local.p}-agent-"
  description = "Trail Desk runtime ENIs"
  vpc_id      = aws_vpc.agents.id
  egress {
    description = "HTTPS out (only private routes exist)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "endpoints" {
  name_prefix = "${local.p}-endpoints-"
  description = "Interface endpoints"
  vpc_id      = aws_vpc.agents.id
  ingress {
    description = "HTTPS from the agent subnets"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.20.100.0/24"]
  }
}

# Bedrock model calls (Converse) over PrivateLink
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.agents.id
  service_name        = "com.amazonaws.${var.region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = false
  tags                = { Name = "${local.p}-bedrock-runtime" }
}

# DynamoDB through a gateway endpoint (free; works by adding routes to route tables)
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.agents.id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  tags              = { Name = "${local.p}-dynamodb" }
}

# ----------------------------------------------------------------- data
resource "aws_dynamodb_table" "stores" {
  name         = "${local.p}-stores"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "store_id"
  attribute {
    name = "store_id"
    type = "S"
  }
}

resource "aws_dynamodb_table_item" "stores" {
  for_each = {
    S01 = { city = "Seattle", address = "1200 Pine St", hours = "Mon-Sat 09:00-20:00, Sun 10:00-18:00" }
    S07 = { city = "Lyon", address = "14 Rue de la Republique", hours = "Mon-Sat 10:00-19:00, Sun closed" }
    S12 = { city = "Pune", address = "FC Road 221", hours = "Daily 10:30-21:30" }
  }
  table_name = aws_dynamodb_table.stores.name
  hash_key   = "store_id"
  item = jsonencode({
    store_id = { S = each.key }
    city     = { S = each.value.city }
    address  = { S = each.value.address }
    hours    = { S = each.value.hours }
  })
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
    sid       = "ReadStores"
    actions   = ["dynamodb:GetItem"]
    resources = [aws_dynamodb_table.stores.arn]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-access"
  role   = module.base.role_name
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_bedrockagentcore_agent_runtime" "trail_desk" {
  agent_runtime_name = "riverbend_m5_trail_desk"
  description        = "Trail Desk in a private VPC (mission 5)"
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
    network_mode = "VPC"
    network_mode_config {
      subnets         = aws_subnet.private[*].id
      security_groups = [aws_security_group.agent.id]
    }
  }

  environment_variables = {
    MODEL_ID    = var.model_id
    STORE_TABLE = aws_dynamodb_table.stores.name
  }

  depends_on = [aws_iam_role_policy.agent, aws_route_table_association.private]
}
