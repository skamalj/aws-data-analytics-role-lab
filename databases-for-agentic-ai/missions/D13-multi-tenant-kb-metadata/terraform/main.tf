# Mission D13 - "Partner A gets partner B's answers"
# One Bedrock Knowledge Base (on Aurora pgvector) serves three partner shops. Each document carries
# its tenant in a metadata sidecar file; every search must be filtered to the caller's tenant.

locals {
  p  = "riverbend-d13"
  db = data.terraform_remote_state.base.outputs
}

data "aws_caller_identity" "me" {}

resource "aws_s3_bucket" "docs" {
  bucket_prefix = "${local.p}-partner-docs-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "docs" {
  for_each = fileset("${path.module}/../docs", "**")
  bucket   = aws_s3_bucket.docs.id
  key      = "partners/${each.value}"
  source   = "${path.module}/../docs/${each.value}"
  etag     = filemd5("${path.module}/../docs/${each.value}")
}

data "aws_iam_policy_document" "kb_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.me.account_id]
    }
  }
}

resource "aws_iam_role" "kb" {
  name_prefix        = "${local.p}-kb-"
  assume_role_policy = data.aws_iam_policy_document.kb_trust.json
}

resource "aws_iam_role_policy" "kb" {
  name = "kb-access"
  role = aws_iam_role.kb.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "bedrock:InvokeModel", Resource = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:ListBucket"], Resource = [aws_s3_bucket.docs.arn, "${aws_s3_bucket.docs.arn}/*"] },
      { Effect = "Allow", Action = "rds:DescribeDBClusters", Resource = local.db.cluster_arn },
      { Effect = "Allow", Action = ["rds-data:ExecuteStatement", "rds-data:BatchExecuteStatement"], Resource = local.db.cluster_arn },
      { Effect = "Allow", Action = "secretsmanager:GetSecretValue", Resource = local.db.kb_secret_arn },
    ]
  })
}

resource "aws_bedrockagent_knowledge_base" "partners" {
  name     = "${local.p}-partners"
  role_arn = aws_iam_role.kb.arn
  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = 1024
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }
  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn           = local.db.cluster_arn
      credentials_secret_arn = local.db.kb_secret_arn
      database_name          = local.db.database
      table_name             = "bedrock_kb.d13_chunks"
      field_mapping {
        primary_key_field     = "id"
        vector_field          = "embedding"
        text_field            = "chunks"
        metadata_field        = "metadata"
        custom_metadata_field = "custom_metadata"
      }
    }
  }
  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "partners" {
  name              = "partner-documents"
  knowledge_base_id = aws_bedrockagent_knowledge_base.partners.id
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.docs.arn
      inclusion_prefixes = ["partners/"]
    }
  }
}

# ----------------------------------------------------------------- search tool
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "search" {
  name_prefix        = "${local.p}-search-"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "search_logs" {
  role       = aws_iam_role.search.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "search" {
  name = "retrieve"
  role = aws_iam_role.search.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "bedrock:Retrieve", Resource = aws_bedrockagent_knowledge_base.partners.arn }]
  })
}

data "archive_file" "search" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/partner_search.py"
  output_path = "${path.module}/build/partner_search.zip"
}

resource "aws_lambda_function" "search" {
  function_name    = "${local.p}-partner-search"
  role             = aws_iam_role.search.arn
  runtime          = "python3.12"
  handler          = "partner_search.handler"
  filename         = data.archive_file.search.output_path
  source_code_hash = data.archive_file.search.output_base64sha256
  timeout          = 30
  environment {
    variables = { KB_ID = aws_bedrockagent_knowledge_base.partners.id }
  }
}
