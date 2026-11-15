output "docs_bucket" { value = aws_s3_bucket.docs.id }
output "ingest_function" { value = module.ingest.function_name }
output "region" { value = var.region }
