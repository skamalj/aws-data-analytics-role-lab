variable "name" { type = string }
variable "source_dir" { type = string }
variable "build_dir" { type = string }
variable "handler" { type = string }
variable "cluster_arn" { type = string }
variable "database" { type = string }

variable "db_secret_arn" {
  description = "Secret the function logs in with (DB_SECRET_ARN)"
  type        = string
}

variable "allowed_secret_arns" {
  description = "Secrets the function's role may read"
  type        = list(string)
}

variable "environment" {
  type    = map(string)
  default = {}
}

variable "extra_policy_json" {
  type    = string
  default = null
}

variable "timeout" {
  type    = number
  default = 30
}

variable "memory_size" {
  type    = number
  default = 256
}
