terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.72.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "larchmont-agent-identity-labs", Challenge = "S1" }
  }
}

data "terraform_remote_state" "base" {
  backend = "local"
  config  = { path = "${path.module}/../../../base/terraform/terraform.tfstate" }
}
