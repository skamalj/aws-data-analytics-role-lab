# A Lambda function that talks to the shared Aurora cluster through the RDS Data API.
# Mission-specific permissions (Bedrock, DynamoDB, S3 ...) come in through extra_policy_json.
terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = ">= 6.72.0" }
    archive = { source = "hashicorp/archive", version = ">= 2.4.0" }
  }
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fn" {
  name_prefix        = "${var.name}-"
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.fn.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "db" {
  name = "database-access"
  role = aws_iam_role.fn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement",
      "rds-data:BeginTransaction", "rds-data:CommitTransaction", "rds-data:RollbackTransaction"], Resource = var.cluster_arn },
      { Effect = "Allow", Action = "secretsmanager:GetSecretValue", Resource = var.allowed_secret_arns },
    ]
  })
}

resource "aws_iam_role_policy" "extra" {
  count  = var.extra_policy_json == null ? 0 : 1
  name   = "mission-access"
  role   = aws_iam_role.fn.id
  policy = var.extra_policy_json
}

data "archive_file" "code" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${var.build_dir}/${var.name}.zip"
  excludes    = ["__pycache__"]
}

resource "aws_lambda_function" "fn" {
  function_name    = var.name
  role             = aws_iam_role.fn.arn
  runtime          = "python3.12"
  handler          = var.handler
  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256
  timeout          = var.timeout
  memory_size      = var.memory_size
  environment {
    variables = merge({ CLUSTER_ARN = var.cluster_arn, DB_SECRET_ARN = var.db_secret_arn, DB_NAME = var.database }, var.environment)
  }
  depends_on = [aws_iam_role_policy.db, aws_iam_role_policy_attachment.logs]
}
