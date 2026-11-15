output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.inspector.agent_runtime_arn }
output "runtime_id" { value = aws_bedrockagentcore_agent_runtime.inspector.agent_runtime_id }
output "runtime_role_arn" { value = module.base.role_arn }
output "memory_table" { value = aws_dynamodb_table.memory.name }
output "region" { value = var.region }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.inspector.agent_runtime_id}-DEFAULT" }
