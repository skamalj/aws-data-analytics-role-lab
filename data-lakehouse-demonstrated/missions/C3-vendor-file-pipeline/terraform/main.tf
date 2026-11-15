# Challenge C3 - vendor file processing pipeline
#   s3://<raw>/vendors/incoming/*.csv -> EventBridge -> Step Functions:
#     Validate (Lambda) -> valid? -> Load (Glue job, Iceberg MERGE) -> move to vendors/processed/
#                                  -> otherwise move to vendors/quarantine/
locals {
  b   = data.terraform_remote_state.base.outputs
  p   = "riverbend-lh-c3"
  raw = "arn:aws:s3:::${local.b.raw_bucket}"
}

# ----------------------------------------------------------------- S3 events
resource "aws_s3_bucket_notification" "raw" {
  bucket      = local.b.raw_bucket
  eventbridge = false
}

# ----------------------------------------------------------------- validation Lambda
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "validate" {
  name_prefix        = "${local.p}-validate-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "validate_logs" {
  role       = aws_iam_role.validate.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "validate" {
  name   = "read-incoming"
  role   = aws_iam_role.validate.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "s3:GetObject", Resource = "${local.raw}/vendors/*" }] })
}

data "archive_file" "validate" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/validate.py"
  output_path = "${path.module}/build/validate.zip"
}

resource "aws_lambda_function" "validate" {
  function_name    = "${local.p}-validate"
  role             = aws_iam_role.validate.arn
  runtime          = "python3.12"
  handler          = "validate.handler"
  filename         = data.archive_file.validate.output_path
  source_code_hash = data.archive_file.validate.output_base64sha256
  timeout          = 60
}

# ----------------------------------------------------------------- Glue load job
module "vendor_load" {
  source         = "../../../common/terraform/iceberg_glue_job"
  name           = "${local.p}-vendor-load"
  script_path    = "${path.module}/../glue/vendor_load.py"
  scripts_bucket = local.b.scripts_bucket
  role_arn       = local.b.glue_role_arn
  warehouse      = local.b.warehouse
  arguments      = { "--database" = local.b.database, "--table" = "vendor_shipments" }
}

# ----------------------------------------------------------------- state machine
data "aws_iam_policy_document" "sfn_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name_prefix        = "${local.p}-sfn-"
  assume_role_policy = data.aws_iam_policy_document.sfn_trust.json
}

resource "aws_iam_role_policy" "sfn" {
  name = "orchestrate"
  role = aws_iam_role.sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "lambda:InvokeFunction", Resource = aws_lambda_function.validate.arn },
      { Effect = "Allow", Action = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:BatchStopJobRun"],
      Resource = "arn:aws:glue:${var.region}:${local.b.account_id}:job/${module.vendor_load.job_name}" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${local.raw}/vendors/*" },
    ]
  })
}

resource "aws_sfn_state_machine" "vendor_files" {
  name     = "${local.p}-vendor-files"
  role_arn = aws_iam_role.sfn.arn
  definition = jsonencode({
    Comment = "Validate, load and archive one vendor file"
    StartAt = "Validate"
    States = {
      Validate = {
        Type           = "Task"
        Resource       = "arn:aws:states:::lambda:invoke"
        Parameters     = { FunctionName = aws_lambda_function.validate.arn, Payload = { "bucket.$" = "$.detail.bucket.name", "key.$" = "$.detail.object.key" } }
        ResultSelector = { "valid.$" = "$.Payload.valid", "rows.$" = "$.Payload.rows", "errors.$" = "$.Payload.errors", "filename.$" = "$.Payload.filename" }
        ResultPath     = "$.validation"
        Next           = "IsValid"
      }
      IsValid = {
        Type    = "Choice"
        Choices = [{ Variable = "$.validation.valid", StringEquals = "true", Next = "Load" }]
        Default = "Quarantine"
      }
      Load = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName   = module.vendor_load.job_name
          Arguments = { "--source_bucket.$" = "$.detail.bucket.name", "--input_key.$" = "$.detail.object.key" }
        }
        ResultPath = "$.load"
        Next       = "CopyToProcessed"
      }
      CopyToProcessed = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:s3:copyObject"
        Parameters = {
          "Bucket.$"     = "$.detail.bucket.name"
          "CopySource.$" = "States.Format('{}/{}', $.detail.bucket.name, $.detail.object.key)"
          "Key.$"        = "States.Format('vendors/processed/{}', $.validation.filename)"
        }
        ResultPath = null
        Next       = "DeleteIncoming"
      }
      Quarantine = {
        Type     = "Task"
        Resource = "arn:aws:states:::aws-sdk:s3:copyObject"
        Parameters = {
          "Bucket.$"     = "$.detail.bucket.name"
          "CopySource.$" = "States.Format('{}/{}', $.detail.bucket.name, $.detail.object.key)"
          "Key.$"        = "States.Format('vendors/quarantine/{}', $.validation.filename)"
        }
        ResultPath = null
        Next       = "DeleteIncoming"
      }
      DeleteIncoming = {
        Type       = "Task"
        Resource   = "arn:aws:states:::aws-sdk:s3:deleteObject"
        Parameters = { "Bucket.$" = "$.detail.bucket.name", "Key.$" = "$.detail.object.key" }
        ResultPath = null
        End        = true
      }
    }
  })
}

# ----------------------------------------------------------------- EventBridge -> Step Functions
data "aws_iam_policy_document" "events_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "events" {
  name_prefix        = "${local.p}-events-"
  assume_role_policy = data.aws_iam_policy_document.events_trust.json
}

resource "aws_iam_role_policy" "events" {
  name   = "start-pipeline"
  role   = aws_iam_role.events.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "states:StartExecution", Resource = aws_sfn_state_machine.vendor_files.arn }] })
}

resource "aws_cloudwatch_event_rule" "vendor_file" {
  name = "${local.p}-vendor-file-arrived"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [local.b.raw_bucket] }
      object = { key = [{ prefix = "vendor/incoming/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.vendor_file.name
  arn      = aws_sfn_state_machine.vendor_files.arn
  role_arn = aws_iam_role.events.arn
}
