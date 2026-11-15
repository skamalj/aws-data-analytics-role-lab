# AgentCore Runtime execution role with the baseline every agent needs (logs, traces, metrics, read its code).
# Identity permissions (workload access tokens, token vault) are attached by each challenge - that's where the faults live.
variable "name" { type = string }
variable "code_bucket" { type = string }

data "aws_caller_identity" "me" {}
data "aws_region" "here" {}

locals {
  account = data.aws_caller_identity.me.account_id
  region  = data.aws_region.here.region
}

resource "aws_iam_role" "this" {
  name_prefix = "${var.name}-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole", Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Condition = { StringEquals = { "aws:SourceAccount" = local.account }, ArnLike = { "aws:SourceArn" = "arn:aws:bedrock-agentcore:${local.region}:${local.account}:*" } }
    }]
  })
}

resource "aws_iam_role_policy" "baseline" {
  name = "baseline"
  role = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"],
      Resource = "arn:aws:logs:${local.region}:${local.account}:log-group:/aws/bedrock-agentcore/runtimes/*" },
      { Effect = "Allow", Action = ["logs:DescribeLogGroups"], Resource = "arn:aws:logs:${local.region}:${local.account}:log-group:*" },
      { Effect = "Allow", Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"], Resource = "*" },
      { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*", Condition = { StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" } } },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = "arn:aws:s3:::${var.code_bucket}/*" },
    ]
  })
}

output "arn" { value = aws_iam_role.this.arn }
output "name" { value = aws_iam_role.this.name }
