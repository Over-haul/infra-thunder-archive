from pulumi import ResourceOptions, ComponentResource, get_stack
from pulumi_azure_native import managedidentity
from pulumi_azuread import (
    application,
    app_role_assignment,
    service_principal,
)
from pulumi_random import random_uuid

from infra_thunder.lib.azure.aad import admin_consent
from infra_thunder.lib.config import get_sysenv
from infra_thunder.lib.tags import get_tags


def _create_apiserver_application(cls, dependency: ComponentResource, endpoint: str):
    """
    Create an AAD Application for the Kubernetes APIServer

    This application is used by the APIServer to verify oauth2 bearer tokens.

    :return: aad application
    """

    app_uuid = random_uuid.RandomUuid("apiserver-app-uuid", opts=ResourceOptions(parent=dependency))

    oauth_uuid = random_uuid.RandomUuid("apiserver-oauth-uuid", opts=ResourceOptions(parent=dependency))

    # create the app registration
    apiserver_app = application.Application(
        f"{get_sysenv()}-apiserver",
        display_name=f"{get_sysenv()} Kubernetes APIServer",
        web=application.ApplicationWebArgs(
            # These are dummy values, not used in the actual auth flow
            homepage_url=f"https://{endpoint}",
            redirect_uris=[f"https://{endpoint}/apiserver"],
        ),
        # Identifier of the application, must not conflict with others
        identifier_uris=[f"api://{get_sysenv()}/apiserver"],
        # Tell us about all groups that the user is part of
        group_membership_claims=["All"],
        required_resource_accesses=[
            application.ApplicationRequiredResourceAccessArgs(
                # Microsoft Graph (AppId: 00000003-0000-0000-c000-000000000000)
                resource_app_id="00000003-0000-0000-c000-000000000000",
                resource_accesses=[
                    application.ApplicationRequiredResourceAccessResourceAccessArgs(
                        # Read directory data (Application Permission)
                        id="7ab1d382-f21e-4acd-a863-ba3e13f7da61",
                        type="Role",
                    ),
                    application.ApplicationRequiredResourceAccessResourceAccessArgs(
                        # Read directory data (Delegated Permission)
                        id="06da0dbc-49e2-44d2-8312-53f166ab848a",
                        type="Scope",
                    ),
                    application.ApplicationRequiredResourceAccessResourceAccessArgs(
                        # Sign in and read user profile
                        id="e1fe6dd8-ba31-4d61-89e7-88639da4683d",
                        type="Scope",
                    ),
                ],
            ),
            application.ApplicationRequiredResourceAccessArgs(
                # Windows Azure Active Directory (Deprecated)
                resource_app_id="00000002-0000-0000-c000-000000000000",
                resource_accesses=[
                    application.ApplicationRequiredResourceAccessResourceAccessArgs(
                        # Sign in and read user profile
                        id="311a71cc-e848-46a1-bdf8-97ff7156d8e6",
                        type="Scope",
                    )
                ],
            ),
        ],
        app_roles=[
            application.ApplicationAppRoleArgs(
                allowed_member_types=["User", "Application"],
                description="Login grants the ability to access the APIServer",
                display_name="APIUsage",
                value="APIUsage",
                id=app_uuid.result,
                enabled=True,
            )
        ],
        api=application.ApplicationApiArgs(
            oauth2_permission_scopes=[
                application.ApplicationApiOauth2PermissionScopeArgs(
                    user_consent_description="Access the Kubernetes APIServer",
                    user_consent_display_name="Access the APIServer",
                    # the definition of insanity is...
                    admin_consent_description="Access the Kubernetes APIServer",
                    admin_consent_display_name="Access the APIServer",
                    id=oauth_uuid.result,
                    enabled=True,
                    type="User",
                    value="Usage",
                )
            ]
        ),
        opts=ResourceOptions(parent=dependency),
    )

    # grant admin consent on this application. User must be a Global Admin
    # or Privileged role administrator and Cloud Application Administrator.
    admin_consent.AdminConsent(
        "app-admin-consent",
        application_id=apiserver_app.application_id,
        opts=ResourceOptions(parent=apiserver_app),
    )

    # create the enterprise application (service principal)
    apiserver_sp = service_principal.ServicePrincipal(
        f"{get_sysenv()}-apiserver",
        application_id=apiserver_app.application_id,
        # if it already exists(???) just import it. thanks terraform, that's handy.
        use_existing=True,
        opts=ResourceOptions(parent=apiserver_app),
    )

    return apiserver_app, apiserver_sp


def _create_client_application(
    cls,
    dependency: ComponentResource,
    endpoint: str,
    apiserver_app: application.Application,
):
    """
    Create the AAD Application used by kubernetes client utilities.
    This application is not used for kubelet authentication, or authentication where a user already has a
    token to access the Azure API.
    See https://github.com/Azure/kubelogin and look for any options that require a `client-id` parameter for a
    list of scenarios that use this application.

    This Application only has the ability to generate a token for itself, and access the APIServer application.

    :return:
    """

    return application.Application(
        f"{get_sysenv()}-client",
        display_name=f"{get_sysenv()} Kubernetes Client",
        web=application.ApplicationWebArgs(
            homepage_url=f"https://{endpoint}/client",
            redirect_uris=[f"https://{endpoint}/client"],
        ),
        identifier_uris=[f"api://{get_sysenv()}/client"],
        required_resource_accesses=[
            application.ApplicationRequiredResourceAccessArgs(
                resource_app_id=apiserver_app.application_id,
                resource_accesses=[
                    application.ApplicationRequiredResourceAccessResourceAccessArgs(
                        # TODO: ???
                        id=apiserver_app.api.oauth2_permission_scopes[0].id,
                        type="Scope",
                    )
                ],
            ),
        ],
        opts=ResourceOptions(parent=apiserver_app),
    )


def _create_bootstrap_msi(
    cls,
    dependency: ComponentResource,
    apiserver_app: application.Application,
    apiserver_sp: service_principal.ServicePrincipal,
):
    """
    Create a MSI that has access to the client application.
    This will be used by kubelogin on the bootstrapping node to provide a consistent identifier for RBAC.

    :return:
    """
    identity = managedidentity.UserAssignedIdentity(
        f"{get_sysenv()}-bootstrapper",
        tags=get_tags(service=get_stack(), role="bootstrapper", group=get_sysenv()),
        **cls.common_args,
        opts=ResourceOptions(parent=apiserver_app),
    )

    app_role_assignment.AppRoleAssignment(
        f"{get_sysenv()}-bootstrapper",
        # related to the app
        resource_object_id=apiserver_sp.object_id,
        app_role_id=apiserver_sp.app_roles[0].id,
        # resource_object_id="<UUID>", # TODO: this needs to be the enterprise application registration (sp) - we don't have one atm, how to get?
        # app_role_id="<UUID>", # TODO!
        # related to the msi
        principal_object_id=identity.principal_id,
        opts=ResourceOptions(parent=identity),
    )

    # authorization.RoleAssignment(
    #     f"{get_sysenv()}-bootstrapper",
    #     scope=client_app.application_id,
    #     principal_id=identity.principal_id,
    #     principal_type=PrincipalType.SERVICE_PRINCIPAL,
    #     role_definition_id=get_role_definition_id("Contributor", scope=client_app.application_id),
    #     opts=ResourceOptions(parent=identity)
    # )

    return identity


def create_kubernetes_aad(cls, dependency: ComponentResource, endpoint: str):
    # create the apiserver application
    apiserver_app, apiserver_sp = _create_apiserver_application(cls, dependency, endpoint)

    # create the kubelet application
    client_app = _create_client_application(cls, dependency, endpoint, apiserver_app)

    # create the client msi and grant it access to the application
    bootstrap_msi = _create_bootstrap_msi(cls, dependency, apiserver_app, apiserver_sp)

    return apiserver_app, bootstrap_msi
