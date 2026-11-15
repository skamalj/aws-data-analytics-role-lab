output "instance_id" { value = aws_instance.agent_host.id }
output "workload_name" { value = local.agent }
output "host_role_name" { value = aws_iam_role.agent_host.name }
