output "database" { value = aws_glue_catalog_database.governed.name }
output "marketing_role_arn" { value = module.marketing.arn }
output "eu_manager_role_arn" { value = module.eu_manager.arn }
