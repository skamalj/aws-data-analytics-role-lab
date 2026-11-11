variable "name_prefix" {
  description = "Prefix for resource names, e.g. riverbend-m1"
  type        = string
}

variable "zip_path" {
  description = "Path to the agent code package built by common/build_agent.sh"
  type        = string
}
