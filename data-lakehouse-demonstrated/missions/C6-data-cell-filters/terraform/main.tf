# Challenge C6 - data cell filters (row + column security) on riverbend_governed_c6.customer_profiles
locals {
  b      = data.terraform_remote_state.base.outputs
  p      = "riverbend-lh-c6"
  db     = "riverbend_governed_c6"
  prefix = "governed/c6/"
  columns = [["customer_id", "string"], ["name", "string"], ["email", "string"], ["region", "string"], ["segment", "string"],
  ["marketing_opt_in", "boolean"], ["credit_score", "int"], ["lifetime_value", "double"]]
}

# ----------------------------------------------------------------- governed storage + catalog
module "location" {
  source = "../../../common/terraform/lf_location"
  name   = local.p
  bucket = local.b.lake_bucket
  prefix = local.prefix
}

resource "aws_s3_object" "data" {
  bucket = local.b.lake_bucket
  key    = "${local.prefix}customer_profiles/data.csv"
  source = "${path.module}/../data/customer_profiles.csv"
  etag   = filemd5("${path.module}/../data/customer_profiles.csv")
}

resource "aws_glue_catalog_database" "governed" {
  name         = local.db
  location_uri = module.location.location
}

resource "aws_glue_catalog_table" "profiles" {
  database_name = aws_glue_catalog_database.governed.name
  name          = "customer_profiles"
  table_type    = "EXTERNAL_TABLE"
  parameters    = { classification = "csv" }
  storage_descriptor {
    location      = "s3://${local.b.lake_bucket}/${local.prefix}customer_profiles/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters            = { "field.delim" = "," }
    }
    dynamic "columns" {
      for_each = local.columns
      content {
        name = columns.value[0]
        type = columns.value[1]
      }
    }
  }
}

# ----------------------------------------------------------------- personas
module "marketing" {
  source           = "../../../common/terraform/lf_persona"
  name             = "${local.p}-marketing"
  account_id       = local.b.account_id
  region           = local.b.region
  athena_workgroup = local.b.athena_workgroup
  athena_bucket    = local.b.athena_bucket
}

module "eu_manager" {
  source           = "../../../common/terraform/lf_persona"
  name             = "${local.p}-eu-manager"
  account_id       = local.b.account_id
  region           = local.b.region
  athena_workgroup = local.b.athena_workgroup
  athena_bucket    = local.b.athena_bucket
}

# ----------------------------------------------------------------- data cell filters
# Marketing: only customers who opted in to marketing; no financial columns (credit_score, lifetime_value).
resource "aws_lakeformation_data_cells_filter" "marketing" {
  table_data {
    database_name    = aws_glue_catalog_database.governed.name
    table_name       = aws_glue_catalog_table.profiles.name
    table_catalog_id = local.b.account_id
    name             = "marketing_opted_in"
    column_wildcard {
      excluded_column_names = ["credit_score"]
    }
    row_filter {
      all_rows_wildcard {}
    }
  }
}

# Regional manager (EU): EU customers only; everything except credit_score.
resource "aws_lakeformation_data_cells_filter" "eu" {
  table_data {
    database_name    = aws_glue_catalog_database.governed.name
    table_name       = aws_glue_catalog_table.profiles.name
    table_catalog_id = local.b.account_id
    name             = "region_eu"
    column_wildcard {
      excluded_column_names = ["credit_score"]
    }
    row_filter {
      filter_expression = "region = 'eu'"
    }
  }
}

# ----------------------------------------------------------------- grants
resource "aws_lakeformation_permissions" "marketing" {
  principal   = module.marketing.arn
  permissions = ["SELECT"]
  data_cells_filter {
    database_name    = aws_glue_catalog_database.governed.name
    table_name       = aws_glue_catalog_table.profiles.name
    table_catalog_id = local.b.account_id
    name             = aws_lakeformation_data_cells_filter.marketing.table_data[0].name
  }
}

resource "aws_lakeformation_permissions" "eu_manager" {
  principal   = module.eu_manager.arn
  permissions = ["SELECT"]
  table {
    database_name = aws_glue_catalog_database.governed.name
    name          = aws_glue_catalog_table.profiles.name
  }
}
