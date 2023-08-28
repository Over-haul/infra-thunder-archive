import yaml
from pulumi import ResourceOptions, Output
from pulumi_aws import iam
from pulumi_kubernetes import provider as kubernetes_provider, core, meta, apiextensions

from ..config import K8sControllerArgs
from ..types import IamAuthenticatorRole


def configure_iam_authenticator(
    bootstrap_role: iam.Role,
    user_roles: list[tuple[IamAuthenticatorRole, iam.Role]],
    cluster_config: K8sControllerArgs,
    provider: kubernetes_provider.Provider,
):
    """
    Update the IAM authenticator ConfigMap on the cluster to allow access

    :param bootstrap_role: Role to be assumed by nodes joining the cluster
    :param user_roles: List of (config, iam.Role) tuples containing the IAM roles to allow access
    :param provider: Pulumi kubernetes provider
    :return:
    """
    # Node bootstrap roles
    node_bootstrap_roles = [
        {
            "rolearn": bootstrap_role.arn.future(),
            "username": "system:node:{{SessionName}}",
            "groups": ["system:bootstrappers", "system:nodes"],
        }
    ]

    # SSO access roles for all clusters
    sso_roles = [
        {
            "rolearn": iam.get_role(name="SSOAdministratorAccess").arn,  # TODO: must find role arn??
            "username": "sso-admin-{{SessionName}}",
            "groups": ["system:masters"],
        }
    ]

    # template-created roles
    user_role_data = [
        {
            "rolearn": iam_role.arn.future(),
            "username": f"iam-{role.name}-{{{{SessionName}}}}",
            "groups": role.permissions,
        }
        for role, iam_role in user_roles
    ]

    # create the eks-style ConfigMap
    core.v1.ConfigMap(
        "aws-auth",
        metadata=meta.v1.ObjectMetaArgs(name="aws-auth", namespace="kube-system"),
        data={
            "mapRoles": Output.from_input(node_bootstrap_roles + sso_roles + user_role_data).apply(
                lambda x: yaml.safe_dump(x), True
            )
        },
        opts=ResourceOptions(parent=provider, provider=provider),
    )

    # create the custom resource definition for iam authenticator
    # conversion of https://github.com/kubernetes-sigs/aws-iam-authenticator/blob/master/deploy/iamidentitymapping.yaml
    # into a pulumi-manageable version
    # note: we could have just used pulumi_k8s.yaml.ConfigFile() to generate this instead of doing it the hard way.. TIL.
    apiextensions.v1.CustomResourceDefinition(
        "aws-auth-crd",
        api_version="apiextensions.k8s.io/v1beta1",
        kind="CustomResourceDefinition",
        metadata=meta.v1.ObjectMetaArgs(name="iamidentitymappings.iamauthenticator.k8s.aws"),
        spec=apiextensions.v1.CustomResourceDefinitionSpecArgs(
            group="iamauthenticator.k8s.aws",
            names=apiextensions.v1.CustomResourceDefinitionNamesArgs(
                plural="iamidentitymappings",
                singular="iamidentitymapping",
                kind="IAMIdentityMapping",
                categories=["all"],
            ),
            scope="Cluster",
            versions=[
                apiextensions.v1.CustomResourceDefinitionVersionArgs(
                    name="v1alpha1",
                    served=True,
                    storage=True,
                    subresources=apiextensions.v1.CustomResourceSubresourcesArgs(
                        status={},
                    ),
                    schema=apiextensions.v1.CustomResourceValidationArgs(
                        open_apiv3_schema=apiextensions.v1.JSONSchemaPropsArgs(
                            type="object",
                            properties={
                                "spec": apiextensions.v1.JSONSchemaPropsArgs(
                                    type="object",
                                    required=[
                                        "arn",
                                        "username",
                                    ],
                                    properties={
                                        "arn": apiextensions.v1.JSONSchemaPropsArgs(type="string"),
                                        "username": apiextensions.v1.JSONSchemaPropsArgs(type="string"),
                                        "groups": apiextensions.v1.JSONSchemaPropsArgs(
                                            type="array",
                                            items=apiextensions.v1.JSONSchemaPropsArgs(type="string"),
                                        ),
                                    },
                                ),
                                "status": apiextensions.v1.JSONSchemaPropsArgs(
                                    type="object",
                                    properties={
                                        "canonicalARN": apiextensions.v1.JSONSchemaPropsArgs(type="string"),
                                        "userID": apiextensions.v1.JSONSchemaPropsArgs(type="string"),
                                    },
                                ),
                            },
                        )
                    ),
                )
            ],
        ),
        opts=ResourceOptions(parent=provider, provider=provider),
    )
