provider "aws" {
  region = var.region
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.31"

  cluster_endpoint_public_access = true

  # ??? ??? ????? ??? ??? ?????? ?? ?????? ????????:
  enable_cluster_creator_admin_permissions = true

  vpc_id     = data.terraform_remote_state.vpc.outputs.vpc_id
  subnet_ids = data.terraform_remote_state.vpc.outputs.private_subnets

  eks_managed_node_groups = {
    cpu-nodes = {
      min_size     = 1
      max_size     = 2
      desired_size = 1

      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.micro"]
      labels = {
        workload = "cpu"
      }
    }
    gpu-nodes = {
      min_size     = 1
      max_size     = 2
      desired_size = 1

      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.micro"]
      labels = {
        workload = "gpu-simulated"
      }
    }
  }

  tags = {
    Environment = "dev"
    Terraform   = "true"
  }
}
