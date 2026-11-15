# Challenge C7 - order status CDC stream: producer -> Amazon Data Firehose (Direct PUT) -> Iceberg table
#   riverbend_lakehouse.order_status, one row per order (insert / update / delete by order_id)
locals {
  b          = data.terraform_remote_state.base.outputs
  p          = "riverbend-lh-c7"
  lake       = "arn:aws:s3:::${local.b.lake_bucket}"
  catalog    = "arn:aws:glue:${local.b.region}:${local.b.account_id}:catalog"
  error_pref = "firehose-errors/c7/"
}

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/${local.p}-order-status"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_stream" "delivery" {
  name           = "DestinationDelivery"
  log_group_name = aws_cloudwatch_log_group.firehose.name
}

# ----------------------------------------------------------------- delivery role
resource "aws_iam_role" "firehose" {
  name_prefix = "${local.p}-firehose-"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "firehose.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "firehose" {
  name = "iceberg-delivery"
  role = aws_iam_role.firehose.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["glue:GetTable", "glue:GetDatabase"],
        Resource = [local.catalog, "arn:aws:glue:${local.b.region}:${local.b.account_id}:database/${local.b.database}",
      "arn:aws:glue:${local.b.region}:${local.b.account_id}:table/${local.b.database}/*"] },
      { Effect = "Allow", Action = ["s3:AbortMultipartUpload", "s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:PutObject", "s3:DeleteObject"],
      Resource = [local.lake, "${local.lake}/*"] },
      { Effect = "Allow", Action = ["logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.firehose.arn}:*" },
    ]
  })
}

# ----------------------------------------------------------------- the stream
resource "aws_kinesis_firehose_delivery_stream" "orders" {
  name        = "${local.p}-order-status"
  destination = "iceberg"

  iceberg_configuration {
    role_arn           = aws_iam_role.firehose.arn
    catalog_arn        = local.catalog
    buffering_interval = 60
    buffering_size     = 1
    retry_duration     = 60
    append_only        = true

    destination_table_configuration {
      database_name          = local.b.database
      table_name             = "order_status"
      s3_error_output_prefix = local.error_pref
    }

    # Every record says what happened to the order: {"order_id": ..., "op": "insert" | "update" | "delete", ...}
    processing_configuration {
      enabled = true
      processors {
        type = "MetadataExtraction"
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{destinationDatabaseName: \"${local.b.database}\", destinationTableName: \"order_status\", operation: .operation}"
        }
      }
    }

    s3_configuration {
      role_arn            = aws_iam_role.firehose.arn
      bucket_arn          = local.lake
      error_output_prefix = local.error_pref
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = aws_cloudwatch_log_stream.delivery.name
    }
  }

  depends_on = [aws_iam_role_policy.firehose]
}
