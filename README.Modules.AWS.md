---
has_children: true
---

# AWS Modules

- **Networking Services**
  - [VPC](modules/infra_thunder/aws/vpc/README.md) - Provides the base Virtual Private Cloud in AWS
  - [Transit Gateway](modules/infra_thunder/aws/transitgateway/README.md) - Links multiple SysEnvs via an AWS Transit Gateway
  - [Pritunl](modules/infra_thunder/aws/pritunl/README.md) - Provides Client VPN services
  - [Route53](modules/infra_thunder/aws/route53/README.md) - SysEnv public and private DNS
- **Security**
  - [Assumable IAM Roles](modules/infra_thunder/aws/iam_roles/README.md) - Assumable roles for containerized applications
  - [SSM](modules/infra_thunder/aws/ssm/README.md) - Common SSM parameters available for other templates
- **Databases, Caching and Storage**
  - [DocumentDB](modules/infra_thunder/aws/_deprecated/documentdb/README.md) - AWS-managed MongoDB compatible database
  - [ElastiCache](modules/infra_thunder/aws/elasticache/README.md) - AWS-managed Redis
  - [RDS](modules/infra_thunder/aws/rds/README.md) - AWS-managed Postgresql
  - [S3](modules/infra_thunder/aws/s3/README.md) - Blob storage
- **Container Orchestration**
  - [Kubernetes Controllers](modules/infra_thunder/aws/k8s/controllers/README.md) - Batteries-included Kubernetes controllers
  - [Kubernetes Agents](modules/infra_thunder/aws/k8s/agents/README.md) - Opinionated Kubernetes agents
