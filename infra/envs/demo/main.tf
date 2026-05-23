terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "ethka-suhaiman-km-tfstate-demo"
    key            = "demo/terraform.tfstate"
    region         = "me-central-2"
    dynamodb_table = "ethka-suhaiman-km-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "suhaiman-km"
      Env       = var.env
      Owner     = "ethka"
      DataClass = "internal"
    }
  }
}

module "network" {
  source              = "../../modules/network"
  env                 = var.env
  vpc_cidr            = var.vpc_cidr
  allowed_egress_fqdns = [
    "api.openai.com",
    "laws.boe.gov.sa",
    "www.sama.gov.sa",
    "my.gov.sa"
  ]
}

module "eks_cluster" {
  source     = "../../modules/eks-cluster"
  env        = var.env
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}

module "rds_postgres" {
  source     = "../../modules/rds-postgres"
  env        = var.env
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}

module "opensearch" {
  source     = "../../modules/opensearch"
  env        = var.env
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}

module "redis" {
  source     = "../../modules/elasticache-redis"
  env        = var.env
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}

module "observability" {
  source     = "../../modules/observability"
  env        = var.env
  cluster_id = module.eks_cluster.cluster_id
}

module "vault_dev" {
  source     = "../../modules/vault-dev"
  env        = var.env
  cluster_id = module.eks_cluster.cluster_id
}

module "domain_and_tls" {
  source      = "../../modules/domain-and-tls"
  env         = var.env
  domain_name = var.domain_name
}
