---
parent: Thunder
nav_order: 0
---

# Thunder Quick Start

Ready? Let's go!

Thunder is split into two repositories:

- Thunder itself
- Thunder sysenv configurations

## Common dependencies

To play around, first ensure you have Python 3.9 installed as your system Python version, then you can run:

```shell
brew install pulumi || curl -fsSL https://get.pulumi.com/ | sh
pip3 install poethepoet poetry
```

## Using Thunder

Once you have installed the dependencies for Thunder itself (`pulumi`, `poetry`, and `poe`), you're ready to start
using Thunder!

### Deploying existing SysEnvs

If you have existing SysEnv configuration, simply `git clone` it, and `poetry install` in the SysEnv directory.
This will cause `poetry` to install the dependencies and configure the environment for Pulumi to function.

```shell
git clone git@github.com:my-org/sysenvs.git
cd sysenvs/aws/example-us-east-1-app-dev
poetry install
pulumi stack select vpc
pulumi preview
```

### Creating new SysEnvs

{: .d-inline-block }
This is a work in progress!
{: .label .label-red }

Creating new SysEnvs can be done by utilizing our provided template repository.
Simply clone it, and use the generators function to have all the requisite files created for you.

### Development dependencies

Thunder itself uses Poetry for dependency management.

1. Clone this repository to somewhere on your computer:  

    ```shell
    git clone git@github.com:org-name/thunder.git
    ```

2. To switch to local `thunder`, edit the `pyproject.toml` for a given SysEnv
   configuration and change the dependency of`ivy_thunder` to point to the path
   where you have cloned `ivy_thunder` to:

   ```text
   ivy-thunder = { path = "/path/to/thunder", extras = ["aws"], develop = true }
   ```

3. Tell Poetry to install the editable version of Thunder:

   ```shell
   # working around a bug in poetry (https://github.com/python-poetry/poetry/issues/3085)
   $ poetry run pip uninstall ivy-thunder
   $ poetry update
   ```

That's it!

Now you can use your favorite IDE to create code-level changes in Thunder and iteratively develop features for a
given SysEnv without needing to make a Git commit for every change.

Be sure to not commit your modified `pyproject.toml` to your SysEnvs repository, as your changes to Thunder
will not automatically propagate.

## Sample CLI Output

Once you have Thunder installed, you should be able to see previews that look like this:

```shell
$ pulumi preview --show-config
Previewing update (vpc):
     Type                                                  Name                        Plan       Info
 +   pulumi:pulumi:Stack                                   aws-us-west-2-app-prod-vpc  create     1 message
 +   └─ pkg:thunder:aws:vpc                                vpc                         create
 +      └─ aws:ec2:Vpc                                     VPC                         create
 +         ├─ aws:ec2:VpcDhcpOptions                       DHCPOptions                 create
 +         ├─ aws:ec2:Eip                                  nat-us-west-2a              create
 +         │  └─ aws:ec2:NatGateway                        nat-us-west-2a              create
 +         ├─ aws:ec2:VpcDhcpOptionsAssociation            DHCPOptionsAssociation      create
 +         └─ aws:ec2:NetworkAcl                           main                        create

Diagnostics:
  pulumi:pulumi:Stack (example-us-west-2-app-prod-vpc):
    Configuration:
        aws:region: us-west-2
        [...]
        vpc:supernet: 10.20.0.0/16

```

In the case there is drift detected you'll see output like below:

```shell
$ pulumi up
Previewing update (aws-us-west-2-app-prod):
     Type                    Name                        Plan       Info
     pulumi:pulumi:Stack     vpc-aws-us-west-2-app-prod
     └─ pkg:thunder:aws:vpc  vpc
 ~      └─ aws:ec2:Vpc       VPC                         update     [diff: ~tags]

Resources:
    ~ 1 to update
    30 unchanged

Do you want to perform this update? details
  pulumi:pulumi:Stack: (same)
    [urn=urn:pulumi:aws-us-west-2-app-prod::vpc::pulumi:pulumi:Stack::vpc-aws-us-west-2-app-prod]
        ~ aws:ec2/vpc:Vpc: (update)
            [id=vpc-099b5cb29498d6d7f]
            [urn=urn:pulumi:aws-us-west-2-app-prod::vpc::pkg:thunder:aws:vpc$aws:ec2/vpc:Vpc::VPC]
            [provider=urn:pulumi:aws-us-west-2-app-prod::vpc::pulumi:providers:aws::default_3_12_1::8d5a14c3-df52-467a-9e91-1b7f7ea957b4]
          ~ tags: {
              ~ Name     : "vpc-example-aws-us-west-2-app-prod-us-west-2" => "vpc-example-aws-us-west-2-app-prod"
              ~ thunder:group: "us-west-2" => "main"
            }

Do you want to perform this update? yes
Updating (aws-us-west-2-app-prod):
     Type                    Name                        Status      Info
     pulumi:pulumi:Stack     vpc-aws-us-west-2-app-prod
     └─ pkg:thunder:aws:vpc  vpc
 ~      └─ aws:ec2:Vpc       VPC                         updated     [diff: ~tags]

Resources:
    ~ 1 updated
    30 unchanged

Duration: 9s
```

## Importing existing resources into a Pulumi stack

If you come across Pulumi attempting to create a resource when it already exists, you could have Pulumi "adopt" this resource using the `pulumi import` command.

```shell
$ pulumi import --help
...

Usage:
  pulumi import [type] [name] [id] [flags]

Flags:
...
      --parent string                         The name and URN of the parent resource in the format name=urn, where name is the variable name of the parent resource
      --protect                               Allow resources to be imported with protection from deletion enabled (default true)
      --provider string                       The name and URN of the provider to use for the import in the format name=urn, where name is the variable name for the provider resource
...
```

We can see that pulumi needs us to specify a `type`, `name` and `id`. There are some optionals, of which we will use `--parent`, `--provider` and `--protect`.

Let's hunt around for the values. Preview a sample set of changes in which pulumi is aware of `my-app-1` but not `my-app-2`.

```shell
$ pulumi preview
Please choose a stack, or create a new one: k8s-controllers
Previewing update (k8s-controllers):
     Type                                                                                Name                                                   Plan       Info
     pulumi:pulumi:Stack                                                                 aws-us-west-2-sandbox-dev-k8s-controllers
     └─ pkg:thunder:aws:k8scontrollers                                                   k8s-controllers
        └─ pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev              aws-us-west-2-sandbox-dev
           └─ pulumi:providers:kubernetes                                                k8s                                                               [diff: ~version]
              ├─ pkg:thunder:helmchartstack:generated:aws-us-west-2-sandbox-dev          aws-abc
              │  └─ kubernetes:helm.sh/v3:Chart                                          aws-abc
 ~            │     └─ kubernetes:apps/v1:Deployment                                     my-app-1                                               update     [diff: ~metadata]
 +            │     └─ kubernetes:apps/v1:Deployment                                     my-app-2                                               create
 ```

Since we want to import `my-app-2`, the type is `kubernetes:apps/v1:Deployment`, name is `my-app-2` and (since this is a kubernetes resource) id is also `my-app-2`.

Now, we'll find the `parent` and `provider` values. Export the stack state to a file.

```shell
pulumi stack export --file temp.json
```

We won't find `my-app-2` here since pulumi isn't aware about it. Instead, find the entry for the sibling with `"id":"my-app-1"` under `'.deployment.resources'`.

```json
{
    "urn": "urn:pulumi:k8s-controllers::aws-us-west-2-sandbox-dev::pkg:thunder:aws:k8scontrollers$pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev$pulumi:providers:kubernetes$pkg:thunder:helmchartstack:generated:aws-us-west-2-sandbox-dev$kubernetes:helm.sh/v3:Chart$kubernetes:apps/v1:Deployment::my-app-1",
    "custom": "...",
    "id": "my-app-1",
    "type": "kubernetes:apps/v1:Deployment",
    "inputs": "...",
    "outputs": "...",
    "parent": "urn:pulumi:k8s-controllers::aws-us-west-2-sandbox-dev::pkg:thunder:aws:k8scontrollers$pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev$pulumi:providers:kubernetes$pkg:thunder:helmchartstack:generated:aws-us-west-2-sandbox-dev$kubernetes:helm.sh/v3:Chart::aws-abc",
    "provider": "urn:pulumi:k8s-controllers::aws-us-west-2-sandbox-dev::pkg:thunder:aws:k8scontrollers$pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev$pulumi:providers:kubernetes::k8s::e47576d4-d728-4fcc-936c-050c1b019971",
    "propertyDependencies": "...",
    "aliases": "..."
}
```

Pulumi wants `parent` and `provider` in the "name:urn" format. `protect` will be false since we want the ability to update and delete the resource.

Putting it all together, our import command is:

```shell
pulumi import 'kubernetes:apps/v1:Deployment' 'my-app-2' 'my-app-2' \
--parent='aws-abc=urn:pulumi:k8s-controllers::aws-us-west-2-sandbox-dev::pkg:thunder:aws:k8scontrollers$pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev$pulumi:providers:kubernetes$pkg:thunder:helmchartstack:generated:aws-us-west-2-sandbox-dev$kubernetes:helm.sh/v3:Chart::aws-abc' \
--provider='k8s=urn:pulumi:k8s-controllers::aws-us-west-2-sandbox-dev::pkg:thunder:aws:k8scontrollers$pkg:thunder:aws:k8scontrollers:cluster:aws-us-west-2-sandbox-dev$pulumi:providers:kubernetes::k8s::e47576d4-d728-4fcc-936c-050c1b019971' \
--protect=false
```
