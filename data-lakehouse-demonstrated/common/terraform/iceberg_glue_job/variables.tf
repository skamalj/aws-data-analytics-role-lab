variable "name" { type = string }
variable "script_path" { type = string }
variable "scripts_bucket" { type = string }
variable "role_arn" { type = string }
variable "warehouse" { type = string }

variable "datalake_formats" {
  description = "Value of --datalake-formats (\"iceberg\" loads the Iceberg libraries into the job)"
  type        = string
  default     = "iceberg"
}

variable "arguments" {
  type    = map(string)
  default = {}
}

variable "workers" {
  type    = number
  default = 2
}

variable "timeout_minutes" {
  type    = number
  default = 20
}
