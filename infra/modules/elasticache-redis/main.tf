resource "aws_elasticache_subnet_group" "this" {
  name       = "suhaiman-${var.env}-redis"
  subnet_ids = var.subnet_ids
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = "suhaiman-${var.env}-redis"
  engine               = "redis"
  node_type            = "cache.t4g.small"
  num_cache_nodes      = 1
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  port                 = 6379
}
