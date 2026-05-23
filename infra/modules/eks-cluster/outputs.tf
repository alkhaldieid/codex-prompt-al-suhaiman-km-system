output "cluster_id" {
  value = aws_eks_cluster.this.id
}

output "general_node_group_id" {
  value = aws_eks_node_group.general.id
}
