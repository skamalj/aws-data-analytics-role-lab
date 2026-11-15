output "tool_function" { value = module.tenant_search.function_name }
output "saas_secret_arn" { value = aws_secretsmanager_secret.saas.arn }
output "region" { value = var.region }
