output "ops_role_arns" { value = { for k, r in aws_iam_role.ops : k => r.arn } }
output "workload_identities" {
  value = {
    advisor    = { name = aws_bedrockagentcore_workload_identity.advisor.name, arn = aws_bedrockagentcore_workload_identity.advisor.workload_identity_arn, owner = "advisory" }
    rebalancer = { name = aws_bedrockagentcore_workload_identity.rebalancer.name, arn = aws_bedrockagentcore_workload_identity.rebalancer.workload_identity_arn, owner = "trading" }
    reporting  = { name = aws_bedrockagentcore_workload_identity.reporting.name, arn = aws_bedrockagentcore_workload_identity.reporting.workload_identity_arn, owner = "compliance" }
  }
}
