output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.rebalancer.agent_runtime_arn }
output "service_role_arn" { value = aws_iam_role.rebalancing_service.arn }
output "ops_console_role_arn" { value = aws_iam_role.ops_console.arn }
