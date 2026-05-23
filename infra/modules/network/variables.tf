variable "env" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "allowed_egress_fqdns" {
  type = list(string)
}
