from enum import Enum


class SubnetPurpose(Enum):
    """
    Enum of supported network purposes.

    "Magic" subnets are subnets that require a specific name to function as the purpose they are named for.
    Delegated subnets can be named arbitrarily, but must have a delegation enabled on them for them to function.
    """

    MAIN = "Main"
    """ Main subnet for all VMs """

    PODS = "Pods"
    """ Subnet used for Kubernetes pods """

    PUBLIC = "Public"
    """ Public subnet for instances with explicit Public IP assignments (no NAT in this subnet) """

    DATABASE = "Database"
    """ Dedicated subnet for Azure database services (to be used with SubnetDelegation) """

    LOAD_BALANCER = "LoadBalancer"
    """ Dedicated subnet for Azure LoadBalancer / Application Gateway. "Magic" subnet name, no delegation required. """

    FIREWALL = "AzureFirewallSubnet"
    """ Dedicated subnet for AzureFirewall. "Magic" subnet name, no delegation required. """

    GATEWAY = "GatewaySubnet"
    """ Dedicated subnet for Azure VPN Gateways. "Magic" subnet name, no delegation required. """

    ROUTESERVER = "RouteServerSubnet"
    """ Dedicated subnet for Azure Route Servers. "Magic" subnet name, no delegation required. """


class SubnetDelegation(Enum):
    """
    Enum of supported subnet delegations.
    Azure requires certain subnets have a subnet that is delegated to them, and the name of the subnet does not matter.
    """

    PostgresFlexibleServers = "Microsoft.DBforPostgreSQL/flexibleServers"
    """ Azure DB for Postgres Flexible Servers delegated subnet """

    @classmethod
    def _missing_(cls, key):
        """
        Hack the enum class to allow getting a valid reference by the name or the value.
        Enum's `__new__` will try by value first, then it will call `__missing__` second.
        """
        return cls[key]
