from dataclasses import dataclass

from pulumi import dynamic, Input, Output


@dataclass
class PrefixListEntryArgs(object):
    prefix_list_id: Input[str]
    cidr: Input[str]
    description: Input[str]


class PrefixListEntryProvider(dynamic.ResourceProvider):
    def create(self, props: PrefixListEntryArgs):
        """
        Add a prefix to the PrefixList
        :param props:
        :return:
        """
        l = (
            g.get_user(props["owner"])
            .get_repo(props["repo"])
            .create_label(
                name=props["name"],
                color=props["color"],
                description=props.get("description", GithubObject.NotSet),
            )
        )
        return dynamic.CreateResult(l.name, props)

    def update(self, id, _olds, props: PrefixListEntryArgs):
        """
        Reconcile a difference between the saved list of prefixes and the current input
        :param id:
        :param _olds:
        :param props:
        :return:
        """
        l = g.get_user(props["owner"]).get_repo(props["repo"]).get_label(id)
        l.edit(
            name=props["name"],
            color=props["color"],
            description=props.get("description", GithubObject.NotSet),
        )
        return dynamic.UpdateResult({**props, **l.raw_data})

    def delete(self, id, props: PrefixListEntryArgs):
        """
        Remove the prefix from the PrefixList entries set
        :param id:
        :param props:
        :return:
        """
        # l = g.get_user(props["owner"]).get_repo(props["repo"]).get_label(id)
        # l.delete()


class PrefixListEntry(dynamic.Resource):
    prefix_list_id: Output[str]
    cidr: Output[str]
    description: Output[str]

    def __init__(self, name, args: PrefixListEntryArgs, opts=None):
        super().__init__(PrefixListEntryProvider(), name, args, opts)
