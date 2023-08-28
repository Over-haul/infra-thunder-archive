from dataclasses import dataclass
from typing import Union, Optional

from pulumi import ResourceOptions, Output
from pulumi_azure_native.authorization import RoleAssignment, PrincipalType
from pulumi_azure_native.compute import VirtualMachine, VirtualMachineScaleSet

from infra_thunder.lib.azure.keyvault import get_sysenv_vault
from .get_role_definition_id import get_role_definition_id


@dataclass
class VMRoleAssignmentArgs:
    scope: Output[str]
    """Scope of the role assignment"""

    role_definition_name: str
    """Name of the role definition"""


def assign_sysenv_vm_roles(
    name: str,
    vm: Union[VirtualMachine, VirtualMachineScaleSet],
    additional_assignments: Optional[list[VMRoleAssignmentArgs]] = None,
) -> None:
    """
    Grant common roles to a VM/VMSS

    :param name: The name of the VM/VMSS
    :param vm: The VM/VMSS
    :param additional_assignments: Additional role assignments to be made on the VM/VMSS
    :return: None
    """

    # allow this vm access to read from shared key vault
    vault_id = get_sysenv_vault().id

    RoleAssignment(
        f"{name}-sysenv-vault-assignment",
        scope=vault_id,
        principal_id=vm.identity.principal_id,
        principal_type=PrincipalType.SERVICE_PRINCIPAL,
        role_definition_id=get_role_definition_id("Key Vault Secrets User", scope=vault_id),
        opts=ResourceOptions(parent=vm),
    )

    for index, args in enumerate(additional_assignments or []):
        RoleAssignment(
            f"{name}-assignment-{index}",
            scope=args.scope,
            principal_id=vm.identity.principal_id,
            principal_type=PrincipalType.SERVICE_PRINCIPAL,
            role_definition_id=get_role_definition_id(args.role_definition_name, scope=args.scope),
            opts=ResourceOptions(parent=vm),
        )
