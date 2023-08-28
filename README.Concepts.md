---
parent: Thunder
nav_order: 1
---

# Thunder and Pulumi Concepts

This document discusses the core concepts of both Pulumi and Thunder

## Pulumi Concepts

To begin, we should first start by explaining how Pulumi works under normal circumstances outside of Thunder.  

Typically, Pulumi divides its operation into three parts:

- **Projects**  
  A collection of different stacks, grouped together in a logical unit. An example of a non-Thunder Pulumi project would be something like `infra`.  
  Projects have a single program with multiple stacks associated with it. A project also has a single state storage location that is common
  for all stacks within it.
- **Stacks**  
  Configuration injected into the program. Typical example would be `dev`, `prod`, `cust1` and so on.
- **Programs**  
  An application written in a supported host language (go, python, nodejs) that takes configuration (from a `stack`)
  and creates resources in a cloud provider.

To sum it up: a Pulumi `project` has one or more `stacks`, and an associated `program` that is invoked with the configuration from the chosen stack.

### State

State is handled by your `login`.  
Pulumi is typically a SaaS product that stores the state of the current project in their cloud service, so in normal circumstances you'd
log into your organization's Pulumi account and create projects and stacks under that.

In Thunder's case, we manage state ourselves in S3, so we use the `local` flag to `pulumi login`,
which allows us to store state in a S3 bucket, separated per SysEnv.

## Thunder Concepts

Thunder redefines some core Pulumi concepts, see below for how we're using Pulumi differently from their documentation.

### SysEnv

Before we get started, let's talk about SysEnvs, what they are, and why you want them.

A `sysenv` is collection of different stacks, grouped together by `namespace`, `provider`, `region`, `purpose`, and `phase`.  
A few examples of a `sysenv` could be:

- `co-az-us-central1-data-prod`
- `co-aws-us-west-2-app-stage`
- `co-aws-us-east-1-sandbox-dev`
- `codefire-office-aus1-corp-prod`

As you can see in the examples above,

- `namespace` is a top-level grouping, usually used to separate businesses from each other.
  Typically, this is a short (three letter ideally) abbreviation of the company name.
- `provider` is the provider where the resources reside. This could be `aws`, `az` (Azure), `gcp`, or even `office`.
- `region` is where these resources exist logically or physically. In a cloud provider, this is the region used for the account.  
  In non-cloud scenarios, this is up to you - but we'd recommend using the closest airport code
  and a number starting at 1 (what happens if you move?).
- `purpose` is typically the business unit that will be using the resources contained in this SysEnv.  
  You may choose to start with `app` and break resources out as time progresses. If your business requires completely
  separate isolation between one business unit and another, use this field of the SysEnv to do so.
- `phase` refers to the deployment phase that resources in this SysEnv represent (`dev`, `prod`, `stage`, etc).  
  > Best practice mandates that you should **never** mix production and non-production resources in the same account. Same goes for SysEnvs.  
  > Don't do it.  
  > You'll make babies everywhere cry, and at some point an auditor will look at you, point, and laugh. Then you'll cry too.  
  > Trust us. You don't want to be untangling that later.
  {: .attention }

#### SysEnv name shortening

Thunder is (painfully) aware that sometimes a SysEnv name can get too long.  
Just try to type `co-aws-us-west-2-sandbox-stage` three times in a row without making a mistake.  
Or, try to create an AWS ALB target group named `co-aws-us-west-2-sandbox-stage-alb` (35 characters, max is 32).

In some places, Thunder will shorten the SysEnv name by hashing it, and keeping two user-identifiable portions of the SysEnv human readable.

This would mean a SysEnv named `co-aws-us-west-2-sandbox-stage` would get shortened to `sandbox-stage-06df3`, allowing
you to differentiate the SysEnvs easily, while avoiding collisions on global resources (S3 buckets).

> The hashing does not guarantee uniqueness, however. There may be a case where two users of Thunder decide to use the same sysenv name, which would mean the hash would be the same.
> There can also be instances where the hash collides. This is a known issue and is under active development.
{: .note }

### Pulumi -> Thunder Terms

If you're familiar with Pulumi at this point, here's a handy Pulumi-to-Thunder translation table:

| Pulumi Term | Thunder Term | Thunder Definition |
| --- | --- | --- |
| `project` | `sysenv` | Collection of different stacks in a Cloud provider account |
| `stack` | `stack` | Configuration used to build a component in the SysEnv |
| `program` | `launcher` | Entrypoint to Thunder |

### Pulumi `project` Structure

Since Thunder utilizes Pulumi's project concept, we need to create a directory skeleton to store the files necessary to make Pulumi happy.
We've chosen to use a terragrunt inspired directory layout for our configuration as well.

Something like this will do just fine:

```shell
github.com/your-org/infrastructure/
└── sysenvs/
    ├── Thunder.common.yaml
    ├── org-aws-us-west-2-app-prod/
    │   ├── Pulumi.yaml
    │   ├── Thunder.common.yaml
    │   ├── thunder.py
    │   └── stacks/
    │       ├── Pulumi.vpc.yaml
    │       ├── Pulumi.rds.yaml
    │       ├── Pulumi.iam.yaml
    │       └── Pulumi.<stack>.yaml
    └── org-aws-us-west-2-app-dev/
        ├── Pulumi.yaml
        ├── Thunder.common.yaml
        ├── thunder.py
        └── stacks/
            ├── Pulumi.vpc.yaml
            ├── Pulumi.rds.yaml
            ├── Pulumi.iam.yaml
            └── Pulumi.<stack>.yaml
```

Let's explain what the files are:

- `org-aws-us.../`  
  SysEnv folder, one of these exists for every SysEnv in your organization.
- `Pulumi.yaml`  
  Contains common Pulumi configuration options. See below for an example of the contents of this file.
- `stacks/Pulumi.*.yaml`  
  Configuration for each stack.
- `Thunder.common.yaml`  
  This file is the 'hierarchical configuration', and is used to set configuration that is inherited by all SysEnvs below it.  
  You can also use this file to override any configuration set by the base configuration.

An example `Pulumi.yaml` contains:

```yaml
name: org-aws-us-west-2-app-dev
main: thunder.py
runtime: python
description: AWS US-West-2 App Dev SysEnv
config: stacks
backend:
  url: s3://org-aws-us-west-2-app-dev-infra/
```

When you run `pulumi stack select vpc; pulumi preview`, Pulumi is launched with the following config:

| Pulumi Config | Value |
| --- | --- |
| login | `s3://org-aws-us-west-2-app-dev-infra/` |
| project | `org-aws-us-west-2-app-dev` |
| stack | `vpc` |
| program | `thunder.py` |

### Thunder.py

What is `thunder.py` in the above example? **Magic, that's what.**

`thunder.py` is the glue that allows us to "pivot" Pulumi's concepts to fit our own.
When you run `pulumi up`, the launcher is called with no arguments, and it is able to discover the name of the current
project and stack that the user is creating.

Once `thunder.py` determines the project and stack (by calling Pulumi's `get_project` and `get_stack` functions)
it calls the launcher of the appropriate Thunder module.

### Thunder Modules

Thunder modules are reusable "blueprints" for creating cloud resources.
Pulumi has it's own called `awsx` that have "best practices" baked into them.  

Think of a Thunder module as our own best practices put into code.

**That means Thunder modules should never contain any code that cannot be released as Open Source!**
