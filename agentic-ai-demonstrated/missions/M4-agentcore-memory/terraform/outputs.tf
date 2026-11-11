output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_arn }
output "auth_mode" { value = "iam" }
output "memory_id" { value = aws_bedrockagentcore_memory.customers.id }
output "runtime_role_name" { value = module.base.role_name }
output "log_group_hint" { value = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.trail_desk.agent_runtime_id}-DEFAULT" }
