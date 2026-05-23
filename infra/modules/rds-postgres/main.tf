resource "aws_db_subnet_group" "this" {
  name       = "suhaiman-${var.env}-postgres"
  subnet_ids = var.subnet_ids
}

resource "aws_db_instance" "this" {
  identifier             = "suhaiman-${var.env}-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.m6g.large"
  allocated_storage      = 100
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.this.name
  username               = "suhaiman_app"
  manage_master_user_password = true
  skip_final_snapshot    = true
  backup_retention_period = 7
}
