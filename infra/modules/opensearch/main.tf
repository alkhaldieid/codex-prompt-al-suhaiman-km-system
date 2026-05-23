resource "aws_opensearch_domain" "this" {
  domain_name    = "suhaiman-${var.env}"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = "r6g.medium.search"
    instance_count = 3
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 30
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }
}
