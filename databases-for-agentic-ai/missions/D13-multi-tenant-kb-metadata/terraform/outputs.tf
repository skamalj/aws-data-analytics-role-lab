output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.partners.id }
output "data_source_id" { value = aws_bedrockagent_data_source.partners.data_source_id }
output "docs_bucket" { value = aws_s3_bucket.docs.id }
output "tool_function" { value = aws_lambda_function.search.function_name }
output "region" { value = var.region }
output "sync_command" {
  value = "aws bedrock-agent start-ingestion-job --region ${var.region} --knowledge-base-id ${aws_bedrockagent_knowledge_base.partners.id} --data-source-id ${aws_bedrockagent_data_source.partners.data_source_id}"
}
