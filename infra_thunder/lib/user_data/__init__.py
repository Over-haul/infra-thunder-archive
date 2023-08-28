import gzip
import inspect
import sys
from base64 import b64encode
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import jinja2
import yaml
from pulumi import Output, ComponentResource, ResourceOptions
from pulumi.output import Inputs

from infra_thunder.lib.config import (
    thunder_env,
    get_stack,
    get_project,
    get_purpose,
    get_phase,
    get_sysenv,
    tag_namespace,
    tag_prefix,
    team,
)
from infra_thunder.lib.prompt_color import get_prompt_color
from infra_thunder.lib.ssm import PARAMETER_STORE_BASE, PARAMETER_STORE_COMMON

DEFAULT_TEMPLATE_NAME = "user_data.sh.j2"

DEFAULT_TEMPLATE_VARIABLES = {
    "prompt_color": get_prompt_color(),
    "project": get_project(),
    "stack": get_stack(),
    "sysenv": get_sysenv(),
    "purpose": get_purpose(),
    "phase": get_phase(),
    "team": team,
    "tag_namespace": tag_namespace,
    "tag_prefix": tag_prefix,
    "parameter_store_base": PARAMETER_STORE_BASE,
    "parameter_store_common": PARAMETER_STORE_COMMON,
}


class UserData(ComponentResource):
    def __init__(
        self,
        resource_name: str,
        replacements: Inputs = {},
        *,
        template_name: str = None,
        include_defaults: bool = True,
        include_cloudconfig: bool = True,
        base64_encode: bool = False,
        opts: ResourceOptions = None,
    ):
        """
        Generate a UserData template from a dictionary of replacements and an optional Jinja2 template.

        If template_name is None, use a default filename (`user_data.sh.j2`) for the template and use the path to the current module to locate it.
        If template_name is an relative path, look in the stack directory (eg: `./mytemplate.sh.j2` = `sysenvs/aws-us-west-2a-app-prod/mytemplate.sh.j2`)
        If template_name is an absolute path, look in the module directory (eg: `mytemplate.sh.j2` = `...python3.9/site-modules/infra_thunder/aws/elasticsearch/mytemplate.sh.j2`)

        UserData will optionally include default variables to the Jinja2 renderer under the `defaults` prefix.
        See `_render_shellscript()` for a list of the defaults included.

        Example::

            subnet = pulumi_aws.ec2.Subnet(
                "my-subnet",
                ...
            )
            pulumi_aws.ec2.Instance(
                "my-instance",
                userdata=UserData(
                    "my-user-data",
                    replacements={
                        "subnet": subnet.id
                    }
                ).template
            )


        :param resource_name: The name of the resource to create
        :param replacements: Dictionary of Pulumi inputs to template into the user data
        :param template_name: Override the default template name.
                If the template name is relative (./) UserData will search the stack (SysEnv) directory,
                otherwise it will search in the Thunder module directory.
        :param include_defaults: Include default template variables in the user data
        :param include_cloudconfig: Generate a cloud-config document for this instance
        :param base64_encode: Base64 encode the returned template
        :param opts: pulumi.ResourceOptions for this resource
        """
        # TODO: make this provider agnostic
        super().__init__(
            f"pkg:thunder:aws:{self.__class__.__name__.lower()}",
            resource_name,
            None,
            opts,
        )
        if replacements is None:
            replacements = {}

        self._template = self._find_template(template_name)
        self._include_defaults = include_defaults
        self._include_cloudconfig = include_cloudconfig
        self._base64_encode = base64_encode
        self._template_vars = Output.from_input(replacements)

    def _find_template(self, template_name):
        """
        Search for template on the filesystem

        If template_name is None, use a default filename for the template and use the path to the current module to locate it.
        If template_name is an relative path, look in the stack directory (eg: `./mytemplate.sh.j2` = `sysenvs/aws-us-west-2a-app-prod/mytemplate.sh.j2`)
        If template_name is an absolute path, look in the module directory (eg: `mytemplate.sh.j2` = `...python3.9/site-modules/infra_thunder/aws/elasticsearch/mytemplate.sh.j2`)

        :param template_name:
        :return:
        """
        if template_name is None:
            template_name = DEFAULT_TEMPLATE_NAME

        if template_name.startswith("./"):
            # template name should be located in the stack directory, so we must find where __main__ lives
            # as it should be the path where the main `thunder.py` launcher lives.
            main_module = sys.modules["__main__"]
            if not hasattr(main_module, "__file__"):
                raise Exception("Can't find __file__ for __main__. Unable to use relative UserData template.")
            return Path(main_module.__file__).absolute() / template_name
        else:
            # template name should be located in the module directory, so we must find where the calling class lives
            # we use inspect for this to both cut down on the amount of self-passing
            # and allow for non class objects to utilize templates located next to them in the filesystem
            # 2 is a magic number here - this is how deep we currently are in the stack
            # 0 is this function itself, 1 is the class itself, and 2 is the calling class/function
            # TODO: figure out better way of finding calling class/function without counting frames
            caller_filename = inspect.stack()[2].filename
            caller_path = Path(caller_filename).parent
            return caller_path / template_name

    def _generate_cloudconfig(self):
        """
        Generate the data that lives in the `text/cloud-config` portion of the cloud-init multipart archive

        :return: Cloud-config MIME part
        """
        thunder_users = [
            {
                "name": user["name"],
                "groups": user["groups"],
                "sudo": "ALL=(ALL) NOPASSWD:ALL",
                "ssh_authorized_keys": user["ssh_authorized_keys"],
            }
            for user in thunder_env.require("ssh_users")
        ]
        users = ["default"] + thunder_users

        cloud_init = {
            "users": users,
            # default is /mnt, we want to move this elsewhere
            "mounts": [["ephemeral0", "/mnt/ephemeral0"]],
        }

        document = MIMEText(yaml.safe_dump(cloud_init), "cloud-config")
        document.add_header("Content-Disposition", "attachment", filename="cloud-config.txt")
        return document

    def _render_shellscript(self, resolved_args):
        """
        Render the shell script using Jinja2

        :param resolved_args: Arguments to be provided to the Jinja renderer
        :return: Shellscript MIME part
        """
        if self._include_defaults:
            resolved_args["defaults"] = DEFAULT_TEMPLATE_VARIABLES
        with open(self._template, "r") as f:
            document = MIMEText(
                jinja2.Template(f.read(), undefined=jinja2.StrictUndefined).render(resolved_args),
                "x-shellscript",
            )
        document.add_header("Content-Disposition", "attachment", filename="shellscript.sh")
        return document

    def _render(self, resolved_args):
        """
        Render the cloud-config and shell scripts (and optionally base64 encodes)

        :param resolved_args: Arguments to be provided to the Jinja renderer
        :return: Rendered MIME multipart archive
        """
        doc = MIMEMultipart(boundary="thunder--user--data--0123456789")
        if self._include_cloudconfig:
            doc.attach(self._generate_cloudconfig())
        doc.attach(self._render_shellscript(resolved_args))

        rendered = (
            b64encode(doc.as_string().encode(encoding="ascii")).decode(encoding="ascii")
            if self._base64_encode
            else doc.as_string()
        )
        return rendered

    def _render_internal(self, resolved_args):
        """
        Render the cloud-config and shell scripts

        :param resolved_args: Arguments to be provided to the Jinja renderer
        :return: Rendered MIME multipart archive
        """
        doc = MIMEMultipart(boundary="thunder--user--data--0123456789")
        if self._include_cloudconfig:
            doc.attach(self._generate_cloudconfig())
        doc.attach(self._render_shellscript(resolved_args))

        return doc.as_string()

    def _compress(self, template):
        """
        Compress and base64 the rendered template string

        This sets mtime on the gzipped file to 0 (unix epoch) to prevent userData changing every render.

        :param template:
        :return:
        """
        return b64encode(gzip.compress(bytes(template, "utf-8"), mtime=0)).decode(encoding="utf-8")

    @property
    def template(self) -> Output[str]:
        """
        Render the template and return it as a pulumi.Output

        :return: Rendered MIME multipart archive
        """
        return self._template_vars.apply(self._render)

    @property
    def gzip_template(self) -> Output[str]:
        """
        Render the template and gzip it, returning as a pulumi.Output

        :return:
        """
        return self._template_vars.apply(self._render_internal).apply(self._compress)
