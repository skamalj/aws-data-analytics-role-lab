output "database" { value = aws_glue_catalog_database.governed.name }
output "data_scientist_role_arn" { value = module.data_scientist.arn }
output "intern_role_arn" { value = module.intern.arn }
