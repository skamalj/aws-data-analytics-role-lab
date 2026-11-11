variable "region" {
  type    = string
  default = "us-west-2"
}

variable "engine_version" {
  description = "Aurora PostgreSQL version (16.3+ is needed for 0-ACU auto-pause)"
  type        = string
  default     = "16.6"
}

variable "min_acu" {
  description = "Minimum capacity. 0 = auto-pause when idle (cheapest); 0.5 = always warm"
  type        = number
  default     = 0
}
