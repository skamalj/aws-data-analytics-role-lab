output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.manuals.id }
output "data_source_id" { value = aws_bedrockagent_data_source.library.data_source_id }
output "docs_bucket" { value = aws_s3_bucket.docs.id }
output "vector_bucket" { value = aws_s3vectors_vector_bucket.kb.vector_bucket_name }
output "vector_index" { value = aws_s3vectors_index.manuals.index_name }
output "runtime_role_name" { value = module.base.role_name }
output "sync_command" {
  description = "Start an ingestion (sync) job"
  value       = "aws bedrock-agent start-ingestion-job --knowledge-base-id ${aws_bedrockagent_knowledge_base.manuals.id} --data-source-id ${aws_bedrockagent_data_source.library.data_source_id} --region ${var.region}"
}
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
