# Challenge S6 - detect identity security events with CloudTrail and CloudWatch
#   CloudTrail -> CloudWatch Logs -> metric filters -> alarms -> SNS, for:
#     * denied token operations (someone trying to act as an agent they don't own)
#     * tampering with workload identities (tags are the ABAC policy, see S1; updates; deletions)
locals {
  b         = data.terraform_remote_state.base.outputs
  p         = "larchmont-s6"
  namespace = "Larchmont/AgentIdentity"
}

# ----------------------------------------------------------------- trail storage
resource "aws_s3_bucket" "trail" {
  bucket_prefix = "${local.p}-trail-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "trail" {
  bucket                  = aws_s3_bucket.trail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "trail" {
  bucket = aws_s3_bucket.trail.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "AclCheck", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:GetBucketAcl", Resource = aws_s3_bucket.trail.arn,
      Condition = { StringEquals = { "aws:SourceArn" = "arn:aws:cloudtrail:${local.b.region}:${local.b.account_id}:trail/${local.p}-identity-audit" } } },
      { Sid       = "Write", Effect = "Allow", Principal = { Service = "cloudtrail.amazonaws.com" }, Action = "s3:PutObject", Resource = "${aws_s3_bucket.trail.arn}/AWSLogs/${local.b.account_id}/*",
        Condition = { StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control", "aws:SourceArn" = "arn:aws:cloudtrail:${local.b.region}:${local.b.account_id}:trail/${local.p}-identity-audit" } }
      },
    ]
  })
}

# ----------------------------------------------------------------- CloudWatch Logs delivery
resource "aws_cloudwatch_log_group" "trail" {
  name              = "/larchmont/cloudtrail/agent-identity"
  retention_in_days = 30
}

resource "aws_iam_role" "trail_to_logs" {
  name_prefix = "${local.p}-trail-logs-"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "cloudtrail.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "trail_to_logs" {
  name = "deliver"
  role = aws_iam_role.trail_to_logs.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["logs:CreateLogStream"], Resource = "${aws_cloudwatch_log_group.trail.arn}:*" }]
  })
}

# ----------------------------------------------------------------- the trail
resource "aws_cloudtrail" "identity" {
  name                          = "${local.p}-identity-audit"
  s3_bucket_name                = aws_s3_bucket.trail.id
  include_global_service_events = true
  enable_log_file_validation    = true
  cloud_watch_logs_group_arn    = "${aws_cloudwatch_log_group.trail.arn}:*"
  cloud_watch_logs_role_arn     = aws_iam_role.trail_to_logs.arn

  advanced_event_selector {
    name = "Management events"
    field_selector {
      field  = "eventCategory"
      equals = ["Management"]
    }
    field_selector {
      field  = "readOnly"
      equals = ["true"]
    }
  }

  depends_on = [aws_s3_bucket_policy.trail, aws_iam_role_policy.trail_to_logs]
}

# ----------------------------------------------------------------- detections
resource "aws_sns_topic" "alerts" {
  name = "${local.p}-identity-alerts"
}

resource "aws_cloudwatch_log_metric_filter" "token_denied" {
  name           = "agentcore-token-access-denied"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"bedrock.amazonaws.com\") && ($.errorCode = \"AccessDenied*\") }"
  metric_transformation {
    name      = "TokenAccessDenied"
    namespace = local.namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "identity_tampering" {
  name           = "agentcore-workload-identity-tampering"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"bedrock-agentcore.amazonaws.com\") && (($.eventName = \"TagResource\") || ($.eventName = \"UntagResource\") || ($.eventName = \"UpdateWorkloadIdentity\") || ($.eventName = \"DeleteWorkloadIdentity\")) }"
  metric_transformation {
    name      = "WorkloadIdentityTampering"
    namespace = local.namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "token_denied" {
  alarm_name          = "${local.p}-token-access-denied"
  alarm_description   = "Someone was denied an AgentCore token operation - possible attempt to act as another agent"
  namespace           = local.namespace
  metric_name         = "TokenAccessDenied"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "identity_tampering" {
  alarm_name          = "${local.p}-workload-identity-tampering"
  alarm_description   = "A workload identity was re-tagged, updated or deleted"
  namespace           = local.namespace
  metric_name         = "WorkloadIdentityTamper"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# ----------------------------------------------------------------- incident simulation targets
resource "aws_bedrockagentcore_workload_identity" "canary" {
  name = "${local.p}-canary-agent"
  tags = { team = "canary" }
}

resource "aws_iam_role" "rogue" {
  name = "${local.p}-rogue-operator"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${local.b.account_id}:root" } }]
  })
}
