variable "env" {
  type    = string
  default = "demo"
}

variable "aws_region" {
  type    = string
  default = "me-central-2"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "domain_name" {
  type    = string
  default = "demo.km.suhaiman.ethka.dev"
}
