# Challenge C5 - tag-based access control (LF-TBAC) on the governed database riverbend_governed_c5
#   s3://<lake>/governed/c5/ is registered with Lake Formation; personas have no S3 access of their own.
locals {
  b      = data.terraform_remote_state.base.outputs
  p      = "riverbend-lh-c5"
  db     = "riverbend_governed_c5"
  prefix = "governed/c5/"
  tables = {
    customers       = { customer_id = "string", name = "string", email = "string", phone = "string", region = "string", segment = "string", lifetime_value = "double" }
    web_sessions    = { session_id = "string", customer_id = "string", page = "string", duration_s = "int", device = "string" }
    product_reviews = { review_id = "string", product_id = "string", rating = "int", review_text = "string" }
    payroll         = { employee_id = "string", name = "string", salary = "int", bank_account = "string" }
  }
  # column order as in the CSV files
  order = {
    customers       = ["customer_id", "name", "email", "phone", "region", "segment", "lifetime_value"]
    web_sessions    = ["session_id", "customer_id", "page", "duration_s", "device"]
    product_reviews = ["review_id", "product_id", "rating", "review_text"]
    payroll         = ["employee_id", "name", "salary", "bank_account"]
  }
}

# ----------------------------------------------------------------- governed storage + catalog
module "location" {
  source = "../../../common/terraform/lf_location"
  name   = local.p
  bucket = local.b.lake_bucket
  prefix = local.prefix
}

resource "aws_s3_object" "data" {
  for_each = local.tables
  bucket   = local.b.lake_bucket
  key      = "${local.prefix}${each.key}/data.csv"
  source   = "${path.module}/../data/${each.key}.csv"
  etag     = filemd5("${path.module}/../data/${each.key}.csv")
}

resource "aws_glue_catalog_database" "governed" {
  name         = local.db
  location_uri = module.location.location
}

resource "aws_glue_catalog_table" "t" {
  for_each      = local.tables
  database_name = aws_glue_catalog_database.governed.name
  name          = each.key
  table_type    = "EXTERNAL_TABLE"
  parameters    = { classification = "csv" }
  storage_descriptor {
    location      = "s3://${local.b.lake_bucket}/${local.prefix}${each.key}/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters            = { "field.delim" = "," }
    }
    dynamic "columns" {
      for_each = local.order[each.key]
      content {
        name = columns.value
        type = each.value[columns.value]
      }
    }
  }
}

# ----------------------------------------------------------------- LF-Tags (the taxonomy)
resource "aws_lakeformation_lf_tag" "domain" {
  key    = "domain"
  values = ["web", "customer", "hr"]
}

resource "aws_lakeformation_lf_tag" "sensitivity" {
  key    = "sensitivity"
  values = ["public", "confidential", "pii"]
}

# ----------------------------------------------------------------- tag assignments
#   table             domain    sensitivity
#   web_sessions      web       public
#   product_reviews   customer  public
#   customers         customer  confidential   (columns email, phone: pii)
#   payroll           hr        confidential
locals {
  table_tags = {
    web_sessions    = { domain = "web", sensitivity = "public" }
    product_reviews = { domain = "customer" }
    customers       = { domain = "customer", sensitivity = "confidential" }
    payroll         = { domain = "hr", sensitivity = "confidential" }
  }
}

resource "aws_lakeformation_resource_lf_tags" "table" {
  for_each = local.table_tags
  table {
    database_name = aws_glue_catalog_database.governed.name
    name          = aws_glue_catalog_table.t[each.key].name
  }
  dynamic "lf_tag" {
    for_each = each.value
    content {
      key   = lf_tag.key
      value = lf_tag.value
    }
  }
  depends_on = [aws_lakeformation_lf_tag.domain, aws_lakeformation_lf_tag.sensitivity]
}

resource "aws_lakeformation_resource_lf_tags" "customers_pii" {
  table_with_columns {
    database_name = aws_glue_catalog_database.governed.name
    name          = aws_glue_catalog_table.t["customers"].name
    column_names  = ["email"]
  }
  lf_tag {
    key   = "sensitivity"
    value = "pii"
  }
  depends_on = [aws_lakeformation_resource_lf_tags.table]
}

# ----------------------------------------------------------------- personas
module "data_scientist" {
  source           = "../../../common/terraform/lf_persona"
  name             = "${local.p}-data-scientist"
  account_id       = local.b.account_id
  region           = local.b.region
  athena_workgroup = local.b.athena_workgroup
  athena_bucket    = local.b.athena_bucket
}

module "intern" {
  source           = "../../../common/terraform/lf_persona"
  name             = "${local.p}-intern"
  account_id       = local.b.account_id
  region           = local.b.region
  athena_workgroup = local.b.athena_workgroup
  athena_bucket    = local.b.athena_bucket
}

# ----------------------------------------------------------------- tag-based grants
# Data science: customer and web data that is public or confidential (never PII, never HR).
resource "aws_lakeformation_permissions" "data_scientist" {
  principal   = module.data_scientist.arn
  permissions = ["SELECT", "DESCRIBE"]
  lf_tag_policy {
    resource_type = "TABLE"
    expression {
      key    = "sensitivity"
      values = ["public", "confidential"]
    }
  }
  depends_on = [aws_lakeformation_lf_tag.domain, aws_lakeformation_lf_tag.sensitivity]
}

# Interns: public data only.
resource "aws_lakeformation_permissions" "intern" {
  principal   = module.intern.arn
  permissions = ["SELECT", "DESCRIBE"]
  lf_tag_policy {
    resource_type = "TABLE"
    expression {
      key    = "domain"
      values = ["web", "customer"]
    }
  }
  depends_on = [aws_lakeformation_lf_tag.domain, aws_lakeformation_lf_tag.sensitivity]
}
