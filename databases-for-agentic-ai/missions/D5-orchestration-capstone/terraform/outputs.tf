output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "orders_function" { value = aws_lambda_function.orders.function_name }
output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.manuals.id }
output "checkpoint_table" { value = aws_dynamodb_table.checkpoints.name }
output "sync_command" {
  value = "aws bedrock-agent start-ingestion-job --region ${var.region} --knowledge-base-id ${aws_bedrockagent_knowledge_base.manuals.id} --data-source-id ${aws_bedrockagent_data_source.manuals.data_source_id}"
}
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
