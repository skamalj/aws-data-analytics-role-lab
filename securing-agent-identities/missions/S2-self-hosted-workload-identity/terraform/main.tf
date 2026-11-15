# Challenge S2 - a self-hosted agent (EC2, managed through Systems Manager) gets an AgentCore workload identity
#   The research agent runs outside AgentCore Runtime, so nothing creates or delivers an identity for it:
#   it reads its workload name from Parameter Store, calls GetWorkloadAccessToken with its instance-role
#   credentials, then exchanges that token at the token vault for the Market Data API key.
locals {
  b      = data.terraform_remote_state.base.outputs
  p      = "larchmont-s2"
  agent  = "${local.p}-research-agent"
  arn    = "arn:aws:bedrock-agentcore:${local.b.region}:${local.b.account_id}"
  params = "/larchmont/research-agent"
}

# ----------------------------------------------------------------- workload identity
# SEC-114: "provision the research agent's workload identity" - still open.

# ----------------------------------------------------------------- configuration (Parameter Store)
resource "aws_ssm_parameter" "workload_name" {
  name  = "${local.params}/workload-name"
  type  = "String"
  value = local.agent
}

resource "aws_ssm_parameter" "provider" {
  name  = "${local.params}/credential-provider"
  type  = "String"
  value = local.b.market_data_provider_name
}

# ----------------------------------------------------------------- instance role
resource "aws_iam_role" "agent_host" {
  name_prefix = "${local.p}-host-"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "agent_host" {
  name = "research-agent"
  role = aws_iam_role.agent_host.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "Code", Effect = "Allow", Action = "s3:GetObject", Resource = "arn:aws:s3:::${local.b.code_bucket}/${local.b.script_key}" },
      { Sid = "Config", Effect = "Allow", Action = ["ssm:GetParameter", "ssm:GetParameters"], Resource = "arn:aws:ssm:${local.b.region}:${local.b.account_id}:parameter${local.params}/*" },
      {
        Sid    = "WorkloadIdentity"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetWorkloadAccessTokenForJWT"]
        Resource = ["${local.arn}:workload-identity-directory/default",
        "${local.arn}:workload-identity-directory/default/workload-identity/${local.agent}"]
      },
      {
        Sid    = "TokenVault"
        Effect = "Allow"
        Action = ["bedrock-agentcore:GetResourceApiKey"]
        Resource = ["${local.arn}:token-vault/default", "${local.arn}:token-vault/default/apikeycredentialprovider/${local.b.market_data_provider_name}",
        "${local.arn}:workload-identity-directory/default", "${local.arn}:workload-identity-directory/default/workload-identity/${local.agent}"]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "agent_host" {
  name_prefix = "${local.p}-host-"
  role        = aws_iam_role.agent_host.name
}

# ----------------------------------------------------------------- the host (no SSH, no inbound ports)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "agent_host" {
  name_prefix = "${local.p}-host-"
  description = "research agent host: outbound HTTPS only"
  vpc_id      = data.aws_vpc.default.id
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "dnf package mirrors"
  }
}

resource "aws_instance" "agent_host" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = "t3.micro"
  subnet_id                   = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids      = [aws_security_group.agent_host.id]
  iam_instance_profile        = aws_iam_instance_profile.agent_host.name
  associate_public_ip_address = true
  user_data_replace_on_change = true
  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }
  user_data = <<-EOT
    #!/bin/bash
    set -e
    dnf install -y python3-pip
    pip3 install "boto3>=1.40"
    mkdir -p /opt/research-agent
    aws s3 cp s3://${local.b.code_bucket}/${local.b.script_key} /opt/research-agent/agent.py
    echo 'AGENT_NAME=research-agent' > /opt/research-agent/env
  EOT
  tags      = { Name = "${local.p}-research-agent-host" }
}
