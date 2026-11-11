output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.manuals.id }
output "data_source_id" { value = aws_bedrockagent_data_source.manuals.data_source_id }
output "kb_role_name" { value = aws_iam_role.kb.name }
output "sync_command" {
  value = "aws bedrock-agent start-ingestion-job --region ${var.region} --knowledge-base-id ${aws_bedrockagent_knowledge_base.manuals.id} --data-source-id ${aws_bedrockagent_data_source.manuals.data_source_id}"
}
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
