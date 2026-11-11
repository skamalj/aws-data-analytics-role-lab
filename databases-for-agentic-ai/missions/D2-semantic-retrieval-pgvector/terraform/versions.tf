terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.72.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "riverbend-db-agentic-labs", Mission = "D2" }
  }
}

data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../../base/terraform/terraform.tfstate" }
}
