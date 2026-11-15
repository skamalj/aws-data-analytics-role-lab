# Shared lakehouse foundation: raw (landing) bucket, lake bucket (Iceberg warehouse), scripts
# bucket, Athena results, the Glue database and an Athena workgroup (engine v3).

data "aws_caller_identity" "me" {}

locals {
  p = "riverbend-lh"
}

resource "aws_s3_bucket" "raw" {
  bucket_prefix = "${local.p}-raw-"
  force_destroy = true
}

resource "aws_s3_bucket" "lake" {
  bucket_prefix = "${local.p}-lake-"
  force_destroy = true
}

resource "aws_s3_bucket" "scripts" {
  bucket_prefix = "${local.p}-scripts-"
  force_destroy = true
}

resource "aws_s3_bucket" "athena" {
  bucket_prefix = "${local.p}-athena-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = { raw = aws_s3_bucket.raw.id, lake = aws_s3_bucket.lake.id, scripts = aws_s3_bucket.scripts.id, athena = aws_s3_bucket.athena.id }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena" {
  bucket = aws_s3_bucket.athena.id
  rule {
    id     = "expire-results"
    status = "Enabled"
    filter {}
    expiration { days = 7 }
  }
}

resource "aws_glue_catalog_database" "lakehouse" {
  name        = "riverbend_lakehouse"
  description = "Riverbend retail lakehouse (Apache Iceberg tables)"
}

resource "aws_athena_workgroup" "lh" {
  name          = local.p
  force_destroy = true
  configuration {
    enforce_workgroup_configuration = true
    engine_version {
      selected_engine_version = "Athena engine version 3"
    }
    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena.id}/results/"
    }
  }
}

# Role shared by the challenges' Glue jobs (each challenge adds what it needs).
data "aws_iam_policy_document" "glue_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name_prefix        = "${local.p}-glue-"
  assume_role_policy = data.aws_iam_policy_document.glue_trust.json
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_data" {
  name = "lakehouse-data"
  role = aws_iam_role.glue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:ListBucket"],
      Resource = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*", aws_s3_bucket.scripts.arn, "${aws_s3_bucket.scripts.arn}/*"] },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      Resource = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/*"] },
      { Effect = "Allow", Action = ["glue:GetDatabase", "glue:GetTable", "glue:GetTables", "glue:UpdateTable", "glue:CreateTable",
      "glue:GetPartitions", "glue:BatchCreatePartition"], Resource = "*" },
    ]
  })
}
