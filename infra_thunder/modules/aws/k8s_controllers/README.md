---
parent: AWS Modules
---

# Kubernetes Controllers

This module provides a batteries-included Kubernetes control plane similar to Kops or Kubeadm.

## Sub-topics

- [Kubeconfigs](#kubeconfigs)
- [DNS](#dns)
- [ClusterIP Routing](#clusterip-routing)
- [Etcd](#etcd)
- [Kube2Iam](#kube2iam)
- [IAM Authenticator](#iam-authenticator)
- [PKI](#pki)
- [Load Balancing and Ingress](#load-balancing-and-ingress)
- [Metrics](#metrics)
- [Running Pods on Controllers](#running-pods-on-controllers)
- [Updating](#updating)

## Provides

AWS Resources:

- Three autoscaling groups, launch templates, and route53 endpoints for each controller
- Common round-robin route53 apiserver endpoint
- IAM roles to allow the controllers to operate
- IAM role for Kubernetes Agents to authenticate to the cluster
- S3 bucket for etcd backups
- ClusterIP routing

Kubernetes Resources:

- Three PKI Certificate Authorities: etcd, kubernetes, apiserver-aggregation (`proxy-ca`)
- Service account root keypair
- Self-healing etcd with automatic backups, based off e2d
- Administrator kubeconfig
- IAM kubeconfig
- CoreDNS
- AWS IAM Authenticator
- AWS EBS CSI
- AWS CNI
- Cross-Cluster roles
- Datadog Monitoring roles
- Kubernetes Metrics Server
- Kubernetes State Metrics (provided by Datadog Agent)
- Kubelet CSR Approver
- Kubernetes Dashboard
- Kube2IAM
- Kubelet role bindings
- Traefik Ingress
- Customizable extra deployments and default namespaces
- Kubelet per controller node

## Caveats

- Creating a new cluster may require two `pulumi up` runs if the Kubernetes resources fail to create
- Deleting the cluster may be difficult, as Pulumi attempts to delete the Kubernetes resources after the cluster itself is deleted
- Renaming a cluster is not supported, and will be very difficult if manually attempted

## Requirements

> **You must be connected to the VPN to be able to use this module**
{: .attention }

- SSO Roles from Ivy Account Tools
- VPC
- SSM parameter for Datadog API key
- Kubernetes AMI shared with this SysEnv
- Pritunl VPN configured

## Configuration and Outputs

[Please check the config dataclass for configuration options, outputs, and documentation]({{ site.aux_links.Github[0] }}/{{ page.dir }}config.py)

Sample `Pulumi.k8s-controllers.yaml`:

```yaml
config:
  aws:region: us-west-2

  k8s-controllers:clusters:
    - # name and cluster_domain are auto generated if not set
      # name: co-aws-us-west-2-sandbox-dev
      # cluster_domain: co-aws-us-west-2-sandbox-dev.thunder
      service_cidr: 10.24.192.0/21
      enable_clusterip_routes: True
#      extra_helm_charts:
#        - chart: sample-chart
#          repo: https://sample-chart.github.io/
#          namespace: example
#          version: 0.1.1
#          values:
#            index:
#              enabled: false
      extra_namespaces:
        - data
```

## Topics

This section will cover implementation details for some features of the Thunder Kubernetes Controllers

### Kubeconfigs

Accessing the cluster can be done with one of two methods:

- A PKI-based `admin` kubeconfig, used for bootstrapping the cluster and failure recovery
- An IAM-enabled kubeconfig that can be given to any cluster user

> The admin kubeconfig should be protected and treated as a secret, as there is no way to revoke or change it (currently).
{: .warning }

To retrieve the kubeconfigs, you can use:

```shell
# admin kubeconfig
pulumi stack output -j --show-secrets | jq -r '."k8s-controllers"[0].admin_kubeconfig'
# iam kubeconfig
pulumi stack output -j --show-secrets | jq -r '."k8s-controllers"[0].iam_kubeconfig'
```

### DNS

As part of this module, Thunder automatically installs CoreDNS and configures it with two cluster domains:

- `cluster.local` for compatibility with off-the-shelf Helm charts
- a cluster-specific domain, named the same as the cluster itself

The cluster-specific domain allows cross-cluster DNS access and should be used any time Pods wish to communicate with
Services hosted in a remote cluster.

This generates a `Corefile` that looks like this:

```text
.:53 {
    errors
    health {
        lameduck 5s
    }
    ready
    kubernetes co-aws-us-west-2-sandbox-dev.thunder cluster.local in-addr.arpa ip6.arpa {
        pods insecure
        fallthrough in-addr.arpa ip6.arpa
        ttl 30
    }
    prometheus 0.0.0.0:9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}
```

#### Host DNS

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Thunder's Kubernetes AMIs can be configured to use `systemd-resolved` to point any queries for domains in the `.thunder` TLD
to the CoreDNS ClusterIP, allowing cluster operators to resolve Kubernetes service domains and other Thunder-specific
DNS features (Node DNS, Non-Kubernetes Service DNS).

#### Cross-Cluster DNS

Peered Kubernetes clusters can be added to the `Corefile` as zones that point to the remote CoreDNS instance
(`.10` the ClusterIP CIDR for the remote SysEnv) like:

```text
co-aws-us-west-2-app-prod.thunder:53 {
    errors
    cache 30
    forward . 10.80.192.10
}
```

#### Node DNS

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Thunder will eventually support resolving DNS names like `k8s-controllers-i-3cdefb18.node.co-aws-us-west-2-sandbox-dev.thunder`
to the `InternalIP` address of the Kubernetes `Node` object with the same name.

This will be accomplished with a custom out-of-tree CoreDNS plugin at a later date.

Node DNS will allow administrators to more easily access nodes in the cluster without needing to look up a hostname or Instance ID to find an IP address.
Just as DNS for Services makes the developer and user experience better, DNS for Nodes will too.

#### Dynamic Non-Kubernetes Service DNS

{: .d-inline-block }
Upcoming Feature
{: .label .label-red }

Advertising services external to Kubernetes (services running on EC2 instances directly) typically requires static configuration
via `ExternalName` resources, which don't handle health checking or many of the other nice features of standard Kubernetes Service objects.

Thunder aims to add support to CoreDNS for advertising services into the cluster via a gossip protocol,
much like Consul's agent.

### PKI

Kubernetes requires multiple Root Certificate Authorities to function:

- `etcd` CA for TLS and Authz:
  - Control plane to control plane communication for etcd replication
  - API Server to etcd
- `kubernetes` CA for TLS and Authz:
  - Kubelet to API Server (fetching pods, tasks, posting status updates)
  - API Server to Kubelet (logs, `kubectl exec`, statistics/monitoring)
  - Kubernetes components (scheduler, controller-manager) to API Server
- API Server Aggregation (`proxy`) CA for TLS and Authz:
  - APIServer to aggregated API Servers (`metrics.k8s.io`, `externalmetrics`, etc)

A `service-account` public/private keypair is also generated by Thunder to allow the Kubernetes Controller Manager to issue
JWT tokens to service accounts.

#### Certificate Rotation

Each Root CA is configured to expire 10 years from creation time, and all certificates generated from these Root CAs
are configured to expire 1 year from creation time.

Rotating certificates in Thunder is easy, simply terminate and replace all controller instances a few months prior
to certificate expiry. Thunder Kubernetes Controllers automatically issue new certificates that expire 1 year from
first boot time.

The `admin` kubeconfig is automatically re-issued by Pulumi whenever the certificate will expire within a quarter of
its validity period (8760 hours * 0.25 = ~91 days). This ensures the `admin` kubeconfig file is always valid and that
multiple valid copies of the `admin` kubeconfig do not exist for long.

Rotating certificates of Kubernetes Agents is easy too, simply terminate and replace the agents as necessary.
Kubernetes will automatically re-issue new Kubelet serving certificates to the instances when they first connect to the cluster.

### Load Balancing and Ingress

> **TL;DR**: Don't make LoadBalancers, make `ClusterIP` services and `Ingress` objects pointing to them
{: .highlight }

In many Kubernetes distributions, using `Service` objects of type `LoadBalancer` is the preferred method of accessing
services outside of the cluster, *however* in Thunder (and many other Kubernetes distributions) the preferred method is
to create `ClusterIP` services and use an `Ingress` object to allow external access.

Thunder utilizes Traefik as the `Ingress` controller and an AWS ALB as the `LoadBalancer` implementation.

This module installs Traefik as a cluster add-on, and the [Kubernetes Agents module](../agents/README.md#load-balancing) handles
creating the ALB and associated target groups.

#### Load Balancing Flow

Traefik is deployed as a Host Network service listening on port `8080` on every Kubernetes agent, and the AWS ALB
is configured to route traffic to a random agent for any external web requests.

External HTTP/HTTPS requests are handled by the ALB, which forwards the traffic to an instance of Traefik on a random
Kubernetes Node in the target group, and Traefik sends that request directly (bypassing `kube-proxy`) to one of the
active `Endpoints` for the `Service`.

Traffic routed through the ALB to the Ingress encounters two round robin "dice rolls":

1. **ALB Target Group node selection**: AWS will randomly select a node from the list of healthy Target Group candidates
2. **Traefik `Endpoint` selection**: Traefik will send traffic to a random `Endpoint` for the given `Service`, even if this
   `Endpoint` is not local to the node that Traefik is executing on.  
   This function is configurable, however the default setting is recommended.

This means that a single external HTTP/HTTPS request can take a maximum of two hops before it reaches the destination
pod hosting the service itself.

```text
                   Kubernetes Node -> Traefik Ingress -> Endpoint Pod IP for Service -> |
Internet -> ALB -> Kubernetes Node                                                      |
                   Kubernetes Node                         Service <- Kubernetes Node <-|
```

While this may seem like a large overhead, the performance penalty is negligible and actually helps to spread out any
load hotspots in the cluster.

There exist other methods of load balancing that have fewer hops, however they tend to be more complicated and require
tighter integration with the cloud provider than what Thunder wishes to provide.

### ClusterIP Routing

In order to provide access to ClusterIP Services to other instances in the same VPC (or Client VPN), Thunder allows
routing of the ClusterIP CIDR (aka Service CIDR) one of two ways:

1. Via the Kubernetes Controllers directly
2. Via the Kubernetes Agents through use of an AWS Gateway Load Balancer
   (see [Kubernetes Agents Documentation](../agents/README.md#gateway-load-balancer), not covered here)

This module can add routes to all Thunder-created route tables in this SysEnv to the Kubernetes control plane instance
in the route table's availability zone, allowing any network interface connected to the VPC (or present on a Client VPN) to access
Kubernetes services directly via IP without needing an internal load balancer.

This allows developers connected to the SysEnv via a Client VPN connection to directly access ClusterIP Services without
needing the overhead of setting up multiple internal load balancers or ingress objects.

A design goal of Thunder is to allow ClusterIP access to remote clusters that are connected via the Transit Gateway, which
reduces the complexity of cross-cluster service to service communication. If a service in one cluster wishes to communicate
with another cluster, it can simply use DNS to resolve the ClusterIP for the remote service and communicate directly with it
as if it were in the same Kubernetes cluster.

Think service meshes but simpler. Keeping the network "flat" and fully routable reduces developer complexity, as now all
Pods and Services are just another IP address on the network, no matter whether you're in-cluster or on a VPN.

#### Considerations and Caveats

AWS does not support failover or standby for VPC Route Table entries. If a Kubernetes control plane instance in az-1
is no longer able to serve routing traffic (`kube-proxy` malfunctions, instance becomes unhealthy, resource contention),
traffic to the ClusterIP CIDR will fail within az-1.

This will not affect resources running their own `kube-proxy` since it intercepts traffic and routes it directly without
utilizing the VPC Route Tables. Client VPN users and other resources (Ec2 instances, lambdas, peered SysEnvs, etc) without `kube-proxy` will
experience a temporary failure in communication while the control plane instance is unavailable.

To work around this, Thunder has begun the work to support routing ClusterIP traffic via an AWS Gateway Load Balancer
with a Target Group connected to the Kubernetes Agents. Once support for Gateway Load Balancer is complete, the option
to route ClusterIP traffic via the control plane instances will remain in an effort to provide low-complexity ClusterIP
routing for smaller/cheaper clusters.

### Etcd

Thunder Kubernetes Controllers utilize a [customized version](//github.com/Over-haul/e2d) of `e2d`,
[a CriticalStack project](//github.com/criticalstack/e2d), that provides a gossip-based `etcd` cluster with automatic
backup/restore, compaction, and worry-free etcd repairs.

Standard etcd requires operator intervention when refreshing nodes, replacing nodes, or scaling. It also requires use of
3rd party software to manage compaction and backup/restore.

E2d automatically heals the cluster in the event that a node becomes unhealthy and rejoins with old data.

#### Backups

Thunder uses E2d to back up the etcd data hourly to an automatically generated S3 bucket that exists in this SysEnv.

E2d uses S3 lifecycle policies to automatically delete backups older than a certain threshold to prevent the backups
bucket from becoming bloated quickly.

#### Cluster Pausing

{: .d-inline-block }
Untested Feature
{: .label .label-yellow }

E2d provides the unique ability to allow cluster administrators to completely delete all Kubernetes controllers and start them at a later
date from a backup of all etcd data in S3 automatically.

This feature has yet to be fully tested in Thunder, however the basic premise is:

- Drain all Kubernetes agents
- Dim all agent Autoscaling Groups to size 0
- Dim all control plane Autoscaling Groups to size 0 (which deletes all control plane EBS volumes)
- At a later date, set each control plane Autoscaling Group back to size 1 and allow the controllers to boot
- E2d will recover the cluster state from the S3 backups bucket
- Set the agent Autoscaling Groups to the size they were before

This allows operators to save money by completely turning off an entire cluster and back on at a later date without needing
to set up any infrastructure.

### Kube2IAM

[Kube2IAM](//github.com/jtblin/kube2iam) automatically scopes the IAM privileges for a running Kubernetes Pod to those specified in an annotation.
This allows cluster operators to assign privileges to individual Pods rather than granting the same access to all Pods
on every Kubernetes node.

Thunder Kubernetes controllers and agents automatically create an IAM policy that allows them to assume
any IAM role in the `services/*` path scope.

See the documentation for the [IAM Assumable Roles](../../iam_roles/README.md) Thunder module for more information about how to create these roles easily.

### IAM Authenticator

Clusters created by Thunder utilize [AWS IAM Authenticator](//github.com/kubernetes-sigs/aws-iam-authenticator) to provide
authentication for users and operators that use the IAM kubeconfig file.

Thunder also creates IAM roles that can be granted to users to allow them to access the Kubernetes cluster without allowing
access to any other AWS resources.

Access to the cluster can be granted independently of access to any AWS resources by:

- Changing the assumed SSO role that the user is granted on login (for SSO users)
- Creating a new IAM user and granting this user `AssumeRole` privileges on the Kubernetes user role

This allows cluster operators to grant access to just the Kubernetes cluster and it's resources without allowing users
to access any of the underlying AWS infrastructure, while ensuring all access is controlled via SSO.

### Metrics

There are many types of component metrics available in Thunder for Kubernetes:

- `etcd`
- `apiserver`
- `controller-manager`
- `scheduler`
- `kube-state-metrics` (metrics about pods, api objects)
- `kube-metrics-server` (pod cpu/memory, node cpu/memory)

Thunder for Kubernetes also exports metrics from many cluster add-ons:

- CoreDNS
- Kube2IAM metrics
- Traefik metrics

Metrics in Thunder are provided by Datadog Agent, which is installed on all Thunder AMIs and configured at boot time by
cloud-init.

> Thunder does not utilize Prometheus annotations, `AlertRules` or any Prometheus specific CRDs.
> This means tools like [Lens](https://lensapp.io) will not show pod statistics until a Datadog addon is published for Lens.
{: .highlight }

#### Publishing Metrics to Datadog

Datadog will receive metrics in three ways:

- Scraping `Services` with Datadog annotations
  - If you annotate a Kubernetes `Service` with the Datadog annotations, one of the Kubernetes Controllers will
    scrape the `Service` periodically and publish metrics to Datadog.
- Scraping `Pods` with Datadog annotations (handled by all kubernetes instances)
  - If you annotate a Kubernetes `Pod` with the Datadog annotations, the Kubernetes Agent running the `Pod` will
    scrape the `Pod` periodically directly and publish metrics to Datadog.
- Scraping docker containers that match Datadog autodiscovery configurations
- Receiving metrics via `statsd` (handled by all kubernetes instances)

##### Pod/Service Annotations

> Non-infrastructure services should utilize `statsd` for publishing metrics to Datadog
{: .important }

Scraping Prometheus metrics, or utilizing a specialized scraper built into the Datadog agent can be accomplished with
annotations on the `Pod` or `Service` object.

Datadog's documentation has an example here: [https://docs.datadoghq.com/agent/kubernetes/integrations/?tab=kubernetes#configuration](https://docs.datadoghq.com/agent/kubernetes/integrations/?tab=kubernetes#configuration)

> If utilizing `Deployments` or `ReplicaSets`, ensure these annotations exist on the `Pod` spec inside the configuration
> *not* the `Deployment` or `ReplicaSet` itself.
{: .hint }

Annotating a `Pod` can be done like this:

```yaml
apiVersion: v1
kind: Pod
# (...)
metadata:
  name: '<POD_NAME>'
  annotations:
    ad.datadoghq.com/<CONTAINER_IDENTIFIER>.check_names: '[<INTEGRATION_NAME>]'
    ad.datadoghq.com/<CONTAINER_IDENTIFIER>.init_configs: '[<INIT_CONFIG>]'
    ad.datadoghq.com/<CONTAINER_IDENTIFIER>.instances: '[<INSTANCE_CONFIG>]'
    # (...)
spec:
  containers:
    - name: '<CONTAINER_IDENTIFIER>'
# (...)
```

Which can look something like this when deployed:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: redis
  annotations:
    ad.datadoghq.com/redis.check_names: '["redisdb"]'
    ad.datadoghq.com/redis.init_configs: '[{}]'
    ad.datadoghq.com/redis.instances: |
      [
        {
          "host": "%%host%%",
          "port":"6379",
          "password":"%%env_REDIS_PASSWORD%%"
        }
      ]  
  labels:
    name: redis
spec:
  containers:
    - name: redis
      image: redis:latest
      ports:
        - containerPort: 6379
```

### Running Pods on Controllers

There may be occasions where you wish to target the control plane nodes for running a given Pod.

The control plane nodes typically reject Pods due to a `NoSchedule` taint. Pods must tolerate this taint in order to be
scheduled and executed on the control plane nodes:

```yaml
spec:
  tolerations:
    - operator: Exists
      effect: NoSchedule
      key: "node-role.kubernetes.io/master"
      value: "true"
    - operator: Exists
      effect: NoSchedule
      key: "node-role.kubernetes.io/control-plane"
      value: "true"
```

> Do not tolerate all `NoSchedule` taints, otherwise you will run your Pods on nodes other than the controllers (dedicated nodes).
{: .warning }

The controllers are registered with the following taints:

- `node-role.kubernetes.io/master=true:NoSchedule`
- `node-role.kubernetes.io/control-plane=true:NoSchedule`

### Updating

#### Prerequisites

You:

1. have followed the steps in the [quickstart](../../../../../README.Quickstart.md) and are in a sysenv (`cd sysenvs/aws/oh-aws-us-west-2-sandbox-dev`)
2. have aws cli configured
3. are connected via VPN to the cluster
4. have handed thunder your ssh key

#### Procedure

Select the k8s-controllers stack

```shell
pulumi stack select k8s-controllers
```

Update the resources in the stack

```shell
pulumi up
```

Once pulumi is done updating, head on over to the AWS console page for EC2 instances and search for "k8s-controllers".

For each of the three nodes now shown, perform the following steps going in order from the oldest instance to the newest.

1. Get the Instance ID (like i-1234567890)
2. Terminate the instance without decrementing desired capacity. `aws autoscaling terminate-instance-in-auto-scaling-group --no-should-decrement-desired-capacity --instance-id i-1234567890`
3. Wait for the autoscaling group to regenerate the instance.
4. Get the "Private IPv4 address" for the new instance and ssh into it.
5. On the instance, `sudo su`.
6. Tail the cloud init logs to ensure it booted successfully `tail -f /var/log/cloud-init*`. If successful, you should eventually see *"finish: modules-final: SUCCESS: running modules for final"*.
7. Do the same with e2d logs `journalctl -e -u e2d` and look for a *"Server is ready!"*.
8. Ensure all k8s related services are started `systemctl`. You should see no reds.
9. Delete the old node from the cluster.
10. To ensure cluster state has stabilized, wait a minute before proceeding to the next instance.
