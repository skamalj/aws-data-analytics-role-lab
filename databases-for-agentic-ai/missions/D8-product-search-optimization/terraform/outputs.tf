output "tool_function" { value = module.product_tools.function_name }
output "region" { value = var.region }
output "dashboard" { value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.search.dashboard_name}" }
