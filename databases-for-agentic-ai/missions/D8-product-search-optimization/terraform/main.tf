# Mission D8 - "Product search is too slow for a conversation"
# Trail Desk's product tools (one Gateway Lambda target) query catalog.products in the shared
# Aurora cluster. Each call reports its latency to CloudWatch (namespace Riverbend/ProductSearch).

locals {
  db = data.terraform_remote_state.base.outputs
}

module "product_tools" {
  source              = "../../../common/terraform/sql_tool_lambda"
  name                = "riverbend-d8-product-tools"
  source_dir          = "${path.module}/../lambdas"
  build_dir           = "${path.module}/build"
  handler             = "product_search.handler"
  cluster_arn         = local.db.cluster_arn
  database            = local.db.database
  db_secret_arn       = local.db.app_secret_arn
  allowed_secret_arns = [local.db.app_secret_arn]
  timeout             = 30
  memory_size         = 512
}

resource "aws_cloudwatch_dashboard" "search" {
  dashboard_name = "riverbend-d8-product-search"
  dashboard_body = jsonencode({
    widgets = [{
      type = "metric", x = 0, y = 0, width = 18, height = 6
      properties = {
        title       = "Product tool latency (p95, ms) - SLA 150 ms"
        region      = var.region
        stat        = "p95"
        period      = 60
        metrics     = [for t in ["search_products", "browse_category", "similar_products"] : ["Riverbend/ProductSearch", "QueryMs", "Tool", t]]
        annotations = { horizontal = [{ value = 150, label = "SLA" }] }
      }
    }]
  })
}
