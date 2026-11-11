# Shared building block used by every mission:
#   - a versioned S3 bucket holding the agent's code package (direct code deployment)
#   - the AgentCore Runtime execution role with the *baseline* permissions every agent needs
#     (logs, traces, metrics, workload identity, reading its own code).
# Mission-specific permissions (models, tools, knowledge bases, memory...) are attached by each mission.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.72.0" }
  }
}

data "aws_caller_identity" "me" {}
data "aws_region" "here" {}

locals {
  account = data.aws_caller_identity.me.account_id
  region  = data.aws_region.here.region
}

resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${var.name_prefix}-code-"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "agent_zip" {
  depends_on = [aws_s3_bucket_versioning.artifacts]
  bucket     = aws_s3_bucket.artifacts.id
  key        = "agent/agent.zip"
  source     = var.zip_path
  etag       = filemd5(var.zip_path)
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${local.region}:${local.account}:*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name_prefix        = "${var.name_prefix}-runtime-"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

data "aws_iam_policy_document" "baseline" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${local.region}:${local.account}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }
  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${local.region}:${local.account}:log-group:*"]
  }
  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
  statement {
    sid     = "WorkloadIdentity"
    actions = ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT", "bedrock-agentcore:GetWorkloadAccessTokenForUserId"]
    resources = [
      "arn:aws:bedrock-agentcore:${local.region}:${local.account}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${local.region}:${local.account}:workload-identity-directory/default/workload-identity/*",
    ]
  }
  statement {
    sid       = "ReadOwnCode"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }
}

resource "aws_iam_role_policy" "baseline" {
  name   = "baseline"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.baseline.json
}
