output "state_machine_arn" { value = aws_sfn_state_machine.vendor_files.arn }
output "job_name" { value = module.vendor_load.job_name }
output "raw_bucket" { value = local.b.raw_bucket }
