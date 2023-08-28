from pulumi import Output, ResourceOptions, ComponentResource
from pulumi_aws import iam

from infra_thunder.lib.aws.kubernetes import get_ssm_path
from infra_thunder.lib.config import get_stack
from infra_thunder.lib.iam import (
    generate_instance_profile,
    generate_assumable_role_policy,
    generate_ecr_policy,
    generate_ssm_policy,
    generate_kubernetes_eni_policy,
)


def create_nodegroup_iam_role(
    cls, dependency: ComponentResource, cluster_name: str, cluster_config: Output
) -> (iam.InstanceProfile, iam.Role):
    def _generate_bootstrap_assumerole(_cls, role: iam.Role):
        """
        Generate a role policy to allow the K8s agent to assume the node bootstrapper role for kubelet bootstrapping
        :param _cls: Calling class object
        :param role: The role to attach this policy to
        :return: iam.RolePolicy
        """
        # The role lives in `k8s-controllers/k8s_controllers[?name==cluster_name]/bootstrap_role_arn`
        cluster_node_bootstrap_role = cluster_config["bootstrap_role_arn"]
        return iam.RolePolicy(
            "sts-assume-k8s-bootstrap",
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["sts:AssumeRole"],
                        "Resource": [cluster_node_bootstrap_role],
                    },
                ]
            },
            opts=ResourceOptions(parent=role),
        )

    return generate_instance_profile(
        cls,
        include_default=True,
        policy_generators={
            generate_kubernetes_eni_policy,
            generate_ssm_policy([f"{get_ssm_path(cluster_name)}/pki/ca.crt"]),
            generate_ecr_policy,
            generate_assumable_role_policy,
            _generate_bootstrap_assumerole,
        },
        name=f"{get_stack()}-{cluster_name}",
        opts=ResourceOptions(parent=dependency),
    )
