---
parent: AWS Modules
---

# VPC

The VPC module provides a standard Virtual Private Cloud network across all SysEnvs.

## Sub-topics

- [Network Design](#network-design)
- [DNS](#dns)

## Provides

- AWS VPC with secondary CIDR
- Public/Private Subnets with Routing Tables
- Network ACLs
- Internet Gateway
- NAT Gateway per Availability Zone
- Standard Security Groups
- Org-shared Prefix List containing SysEnv Supernet
- Prefix List for peered SysEnvs
- VPC Endpoints for S3 and EC2
- Default EC2 keypairs

## Caveats

None known at this time.

## Requirements

- SSM

## Configuration and Outputs

[Please check the config dataclass for configuration options, outputs, and documentation](config.py)

Sample `Pulumi.vpc.yaml`:

```yaml
config:
  aws:region: us-west-2

  vpc:supernet: 10.24.0.0/16

  vpc:cidr: 10.24.0.0/18
  vpc:secondary_cidrs:
    - 10.24.64.0/18

  vpc:create_endpoints: true
  vpc:create_nat: true
  vpc:allow_internal_ssh: true
  # Auto generated if not set
  #vpc:domain_name: co-aws-us-west-2-sandbox-dev.thunder
  vpc:public_subnets:
    - availability_zone: us-west-2a
      cidr_block: 10.24.0.0/21
      purpose: public
      preferred: True
    - availability_zone: us-west-2b
      cidr_block: 10.24.8.0/21
      purpose: public
    - availability_zone: us-west-2c
      cidr_block: 10.24.16.0/21
      purpose: public
  vpc:private_subnets:
    - availability_zone: us-west-2a
      cidr_block: 10.24.24.0/21
      purpose: private
      preferred: True
    - availability_zone: us-west-2b
      cidr_block: 10.24.32.0/21
      purpose: private
    - availability_zone: us-west-2c
      cidr_block: 10.24.40.0/21
      purpose: private
    # pods (note: these exist in secondary CIDR)
    - availability_zone: us-west-2a
      cidr_block: 10.24.64.0/20
      purpose: pods
    - availability_zone: us-west-2b
      cidr_block: 10.24.80.0/20
      purpose: pods
    - availability_zone: us-west-2c
      cidr_block: 10.24.96.0/20
      purpose: pods

```

<!-- markdownlint-disable MD025 -->

# Topics

## Network Design

Thunder proposes a fairly complex VPC consisting of a `/16` Supernet broken into:

- One primary `/18` containing:
  - Three `/21` public subnets for EC2 instances requiring direct (NAT-less) Internet access or Elastic IP support
  - Three `/21` private subnets for all other EC2 instances
- One secondary `/18` containing:
  - Three `/20` subnets for Kubernetes Pods
- One unused `/18` for future expansion
- One `/18` containing all virtual network services
  - One virtual `/21` for Kubernetes ClusterIPs (see [Kubernetes Controllers](../k8s/controllers/README.md) for more information)
  - One virtual `/24` for VPN Clients (see [Pritunl](../pritunl/README.md) for more information)

<table>
<tbody>
  <tr>
    <th colspan="3">SysEnv Network</th>
  </tr>
  <tr>
    <th rowspan="12" class="bg-grey-lt-100">10.0.0.0/16<br>Supernet</th>
    <th rowspan="6" class="bg-grey-lt-000">10.0.0.0/18<br>Public/Private<br>Subnets<br></th>
    <td>10.0.0.0/21<br>Public AZ1</td>
  </tr>
  <tr>
    <td>10.0.8.0/21<br>Public AZ2</td>
  </tr>
  <tr>
    <td>10.0.16.0/21<br>Public AZ3</td>
  </tr>
  <tr>
    <td>10.0.24.0/21<br>Private AZ1</td>
  </tr>
  <tr>
    <td>10.0.32.0/21<br>Private AZ2</td>
  </tr>
  <tr>
    <td>10.0.40.0/21<br>Private AZ3</td>
  </tr>
  <tr>
    <th rowspan="3" class="bg-grey-lt-000">10.0.64.0/18<br>Pod Subnets<br></th>
    <td>10.0.64.0/20<br>Pods AZ1</td>
  </tr>
  <tr>
    <td>10.0.80.0/20<br>Pods AZ2</td>
  </tr>
  <tr>
    <td>10.0.96.0/20<br>Pods AZ3</td>
  </tr>
  <tr>
    <th class="bg-grey-lt-000">10.0.128.0/18<br>Unused<br></th>
    <td>10.0.128.0/18<br>Unused<br>(Future Expansion)<br></td>
  </tr>
  <tr>
    <th rowspan="2" class="bg-grey-lt-000">10.0.192.0/18<br>Virtual</th>
    <td>10.0.192.0/21<br>ClusterIP Services</td>
  </tr>
  <tr>
    <td>10.0.255.0/24<br>VPN Clients<br></td>
  </tr>
</tbody>
</table>

The virtual subnets live outside of the primary and secondary CIDR for the VPC to work around an AWS limitation,
as Route Table to cannot contain routes to a destination that is within the VPC CIDR.

Some configuration for these virtual subnets exists in the associated Thunder module. Be sure to read their
documentation as well!

Thunder attempts to eliminate NAT from the network where possible by making Kubernetes Pods, Kubernetes ClusterIP Services,
and VPN Clients into routable addresses.

Thunder also attempts to allow naive resources (EC2 instances with no customization, vendor appliances) to access Kubernetes
resources as if they were just another machine on the network.

### Concepts

- **Supernet**: a CIDR that encompasses all subnets in a given SysEnv
- **Pod Subnet**: a subnet that Kubernetes Pods (docker containers) can allocate Elastic Network Interface secondary IPs in
- **ClusterIP Subnet**: virtual "load balancers" exist in this CIDR, traffic to this CIDR is routed via the Kubernetes control plane
- **VPN Client Subnet**: clients connected to the Pritunl Client VPN receive IP addresses in this CIDR, eliminating NAT from the internal network entirely

## DNS

Thunder recommends setting the VPC DNS suffix to the same suffix that the primary Kubernetes cluster uses, and the primary
resolver remain `AmazonProvidedDNS` to ensure interruptions to the Kubernetes control plane not cause cluster-wide name resolution failure.

Setting the DNS suffix to match the Kubernetes cluster CoreDNS name allows hosts to automatically receive the proper DNS suffix
that CoreDNS will allow the resolution of.
