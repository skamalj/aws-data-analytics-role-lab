output "tool_function" { value = module.fast_answer.function_name }
output "cache_table" { value = aws_dynamodb_table.embedding_cache.name }
output "region" { value = var.region }
