---
parent: AWS Modules
---

# Kubernetes Agents

In conjunction with the [Kubernetes Controllers](../k8s_controllers/README.md), this module creates a configurable number of
Kubernetes Agents that run workloads for a given Kubernetes Cluster and act as targets for an AWS ALB.

## Sub-topics

- [Load Balancing](#load-balancing)
- [Gateway Load Balancer](#gateway-load-balancer)
- [Spot Instances](#spot-instances)
- [Cluster Autoscaling](#cluster-autoscaling)
- [Dedicated Nodes](#dedicated-nodes)
- [GPU-Enabled Nodes](#gpu-enabled-nodes)

## Provides

AWS Resources:

- Individual Autoscaling Groups for each NodeGroup
- ALB per ingress-enabled NodeGroup
- ALB request log S3 bucket
- Optional Gateway Load Balancer (GLB) to support ClusterIP routing

Kubernetes Resources:

- Kubelets

## Caveats

## Requirements

> **You must have configured the Kubernetes Controllers before using this module.**  
> This module will fail to configure if the Controllers do not exist.
{: .attention }

## Configuration and Outputs

[Please check the config dataclass for configuration options, outputs, and documentation]({{ site.aux_links.Github[0] }}/{{ page.dir }}config.py)

Sample `Pulumi.k8s-agents.yaml`:

```yaml
config:
  aws:region: us-west-2

  k8s-agents:agents:
    - # temporarily disable GLB, use controllers as clusterip endpoint
      enable_glb: false
      nodegroups:
        - name: default
          instance_type: t3.xlarge
          count: 1
          labels:
            - default_node
            - general
        - name: data
          count: 2
          labels:
            - data
          ingress: false

```

<!-- markdownlint-disable MD025 -->

# Topics

This section will cover implementation details for some features of the Thunder Kubernetes Controllers

## Load Balancing

## Gateway Load Balancer

## Spot Instances

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Spot

## Cluster Autoscaling

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Auto

## Dedicated Nodes

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Dedicate

## GPU-Enabled Nodes

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

GPU
