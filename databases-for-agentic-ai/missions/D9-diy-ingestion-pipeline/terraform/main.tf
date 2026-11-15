# Mission D9 - "Uploaded, but never searchable"
# Do-it-yourself RAG ingestion: documents dropped in S3 are chunked, embedded with Titan V2 and
# written to pgvector by a Lambda function triggered through EventBridge.

locals {
  p  = "riverbend-d9"
  db = data.terraform_remote_state.base.outputs
}

data "aws_caller_identity" "me" {}

resource "aws_s3_bucket" "docs" {
  bucket_prefix = "${local.p}-docs-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "docs" {
  bucket      = aws_s3_bucket.docs.id
  eventbridge = true
}

module "ingest" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "${local.p}-ingest"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "ingest.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = local.db.kb_secret_arn
  allowed_secret_arns = [local.db.kb_secret_arn]
  timeout             = 300
  memory_size         = 512
  extra_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "s3:GetObject", Resource = "${aws_s3_bucket.docs.arn}/*" },
      { Effect = "Allow", Action = "bedrock:InvokeModel", Resource = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0" },
    ]
  })
}

resource "aws_cloudwatch_event_rule" "uploaded" {
  name = "${local.p}-document-uploaded"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [aws_s3_bucket.docs.id] }
      object = { key = [{ suffix = ".txt" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "ingest" {
  rule = aws_cloudwatch_event_rule.uploaded.name
  arn  = module.ingest.function_arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.ingest.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.uploaded.arn
}
