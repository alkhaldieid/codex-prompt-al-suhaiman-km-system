variable "env" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "general_node_instance_types" {
  type    = list(string)
  default = ["m6i.xlarge"]
}
