output "tool_function" { value = module.review_insights.function_name }
output "aurora_ml_role_arn" { value = aws_iam_role.aurora_ml.arn }
output "cluster_id" { value = local.db.cluster_id }
output "region" { value = var.region }
