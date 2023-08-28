from uuid import uuid4

import requests
from pulumi import Output, Input
from pulumi.dynamic import ResourceProvider, Resource, CreateResult
from pulumi_azure_native import authorization

MAX_RETRIES = 10


class AdminConsentProvider(ResourceProvider):
    """
    Dynamic Pulumi provider to create the Admin Consent in the Azure Portal for an Application Registration.

    This provider uses some "private" Azure APIs, however the Azure CLI uses them too, so this seems like fair game.
    (sorry Microsoft, please don't revoke my Windows license or delete me from the internet!)

    See here for the inspiration: https://github.com/Azure/azure-cli/blob/3c3407952bf427c8f3381e4ab27e148bf8b29eb6/src/azure-cli/azure/cli/command_modules/role/custom.py#L994

    Pulumi dynamic providers work just like Terraform providers - except they're written in Python.
    They act on the statefile and should be able to appropriately add/delete/diff/update the resource they create.

    In Pulumi, they need to be fairly simple Python code. They cannot access state in the greater python application,
    and they run in their own thread, so you cannot call any Pulumi runtime functions. This means you need to pass in
    anything they need to operate. You also need to be aware that anything passed into it as a `prop` is potentially
    persisted in the statefile - so don't pass user auth tokens as props, since anyone with the statefile encryption
    key could read the token back out and act as the user that generated the token.

    In our case, we pass the token into the provider at creation time.
    This ensures the token is not persisted in the statefile.
    """

    def __init__(self, token):
        super().__init__()
        self.token = token

    def create(self, props):
        # wait for the application to exist - sometimes it doesn't...
        # for i in range(0,MAX_RETRIES):
        #     # try to read the application id
        #     log.debug(f"Waiting for Application ID, attempt {i}/{MAX_RETRIES}", resource=props["resource"])
        #     pass

        # grant admin consent
        url = f"https://main.iam.ad.ext.azure.com/api/RegisteredApplications/{props['application_id']}/Consent?onBehalfOfAll=true"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "x-ms-client-request-id": str(uuid4()),
        }
        response = requests.post(url, headers=headers, data=None)

        # raise an error (get a traceback) if unsuccessful
        response.raise_for_status()

        return CreateResult(props["application_id"])


class AdminConsent(Resource):
    application_id: Input[str]

    def __init__(self, resource_name, application_id, opts=None):
        self.application_id = Output.from_input(application_id)
        # this resource ID is actually the Azure Portal's dynamic resource ID
        # see the source azure-cli code above for where this magic uuid comes from
        token = authorization.get_client_token(endpoint="74658136-14ec-4630-ad9b-26e160ff0fc6")
        super().__init__(
            AdminConsentProvider(token=token.token),
            resource_name,
            {
                # props dict passed to the provider
                "application_id": self.application_id,
            },
            opts,
        )
