import collections.abc

from pulumi import ResourceOptions, ComponentResource
from pulumi_kubernetes import helm

from .config import HelmChart


def deep_update(source, overrides):
    """
    Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    Source: https://stackoverflow.com/a/30655448
    """
    for key, value in overrides.items():
        if isinstance(value, collections.Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source


def _noawait(obj, opts):
    """
    Pulumi attempts to wait for resources to be created, which leads to deadlocking when a helm chart creates
    resources in an order that will never satisfy the wait condition.

    i.e. chart creates 100 resources - one of which is a Service and another is a Deployment. Pulumi may
    attempt to create 50 resourcess at a time in a "task bucket", and that bucket may include the Service but not the
    Deployment for that service. Since Pulumi will wait for all tasks in the bucket to complete before moving to the
    next set of resources to create the Service object will cause an infinite wait since the Deployment object for that
    Service will never be created.
    """
    if obj.get("metadata"):
        deep_update(obj["metadata"], {"annotations": {"pulumi.com/skipAwait": "true"}})


def _nostatus(obj, opts):
    """
    This is a work-around for the issue described in https://github.com/pulumi/pulumi-kubernetes/issues/1481
    """
    if obj["kind"] == "CustomResourceDefinition" and obj.get("status"):
        del obj["status"]


class HelmChartStack(ComponentResource):
    """
    This class exists to allow Pulumi to create multiple Helm charts in the same "root" stack where the Helm charts
    render the same resource names.

    Example:
        Cluster1 has Helm chart "cillium"
        Cillium Helm chart renders a resource called "cillium-operator"
        Cluster2 has Helm chart "cillium"
        Helm chart renders to same resource, and same resource URN

    This class fixes this issue by "inserting" a new dynamically named stack into the URN, where this stack is named
    based off the name of the resource being created.

    Before:
        'urn:pulumi:k8s-controllers::sysenv-1::pkg:thunder:aws:k8scontrollers$aws:eks/cluster:Cluster$pulumi:providers:kubernetes$kubernetes:helm.sh/v3:Chart$kubernetes:rbac.authorization.k8s.io/v1:ClusterRoleBinding::cilium';
    After:
        'urn:pulumi:k8s-controllers::sysenv-1::pkg:thunder:aws:k8scontrollers$aws:eks/cluster:Cluster$pulumi:providers:kubernetes$pkg:thunder:helmchartstack:generated:myclustername$kubernetes:helm.sh/v3:Chart$kubernetes:rbac.authorization.k8s.io/v1:ClusterRoleBinding::cilium';
    """

    def __init__(self, name: str, namespace: str, chart: HelmChart, opts: ResourceOptions):
        super().__init__(
            f"pkg:thunder:{self.__class__.__name__.lower()}:generated:{namespace}",
            name,
            None,
            opts,
        )
        self.name = name
        self.opts = opts
        self.chart = chart

        self.configure()

    def configure(self):
        helm.v3.Chart(
            self.name,
            config=helm.v3.ChartOpts(
                chart=self.chart.chart,
                namespace=self.chart.namespace,
                fetch_opts=helm.v3.FetchOpts(repo=self.chart.repo, version=self.chart.version),
                values=self.chart.values,
                transformations=[_noawait, _nostatus]
                + (self.chart.transformations if self.chart.transformations else []),
                skip_crd_rendering=self.chart.skip_crd_rendering,
            ),
            opts=ResourceOptions(parent=self, provider=self.opts.provider),
        )


class HelmChartComponent(ComponentResource):
    """
    This is an alternative to HelmChartStack that does not rely on generated URNs to namespace charts.
    You must properly parent objects to ensure no collisions, though.
    """

    def __init__(self, name: str, chart: HelmChart, opts: ResourceOptions):
        super().__init__(f"pkg:thunder:{self.__class__.__name__.lower()}", name, None, opts)
        self.name = name
        self.opts = opts
        self.chart = chart

        self.configure()

    def configure(self):
        helm.v3.Chart(
            self.name,
            config=helm.v3.ChartOpts(
                chart=self.chart.chart,
                namespace=self.chart.namespace,
                fetch_opts=helm.v3.FetchOpts(repo=self.chart.repo, version=self.chart.version),
                values=self.chart.values,
                transformations=[_noawait, _nostatus]
                + (self.chart.transformations if self.chart.transformations else []),
                skip_crd_rendering=self.chart.skip_crd_rendering,
            ),
            opts=ResourceOptions(parent=self, provider=self.opts.provider),
        )


class HelmChartComponent(ComponentResource):
    """
    This is an alternative to HelmChartStack that does not rely on generated URNs to namespace charts.
    You must properly parent objects to ensure no collisions, though.
    """

    def __init__(self, name: str, chart: HelmChart, opts: ResourceOptions):
        super().__init__(f"pkg:thunder:{self.__class__.__name__.lower()}", name, None, opts)
        self.name = name
        self.opts = opts
        self.chart = chart

        self.configure()

    def configure(self):
        helm.v3.Chart(
            self.name,
            config=helm.v3.ChartOpts(
                chart=self.chart.chart,
                namespace=self.chart.namespace,
                fetch_opts=helm.v3.FetchOpts(repo=self.chart.repo, version=self.chart.version),
                values=self.chart.values,
                transformations=[_noawait, _nostatus],
                skip_crd_rendering=self.chart.skip_crd_rendering,
            ),
            opts=ResourceOptions(parent=self, provider=self.opts.provider),
        )
