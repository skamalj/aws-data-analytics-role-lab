# A Glue 5.0 Spark job that works with Apache Iceberg tables in the Glue Data Catalog.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.72.0" }
  }
}

locals {
  iceberg_conf = join(" --conf ", [
    "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
    "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
    "spark.sql.catalog.glue_catalog.warehouse=${var.warehouse}",
  ])
  args = merge(
    var.datalake_formats == "" ? {} : { "--datalake-formats" = var.datalake_formats },
    {
      "--conf"                             = local.iceberg_conf
      "--enable-glue-datacatalog"          = "true"
      "--enable-continuous-cloudwatch-log" = "true"
      "--job-bookmark-option"              = "job-bookmark-disable"
    },
    var.arguments,
  )
}

resource "aws_s3_object" "script" {
  bucket = var.scripts_bucket
  key    = "glue/${var.name}/${basename(var.script_path)}"
  source = var.script_path
  etag   = filemd5(var.script_path)
}

resource "aws_glue_job" "job" {
  name              = var.name
  role_arn          = var.role_arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = var.workers
  timeout           = var.timeout_minutes
  max_retries       = 0
  execution_property {
    max_concurrent_runs = 1
  }
  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.scripts_bucket}/${aws_s3_object.script.key}"
  }
  default_arguments = local.args
}
