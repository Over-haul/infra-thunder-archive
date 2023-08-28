# Setup a new System Environment (SysEnv)

## Overview

Here you'll find the necessary steps for creating and/or setting up a new
 System Environment (SysEnv)

## Requirements

- Thunder requirements - can be found
  [here](https://github.com/Over-haul/infra-thunder-public/blob/master/README.Quickstart.md#thunder-quick-start)
  - Python 3.9+
  - pulumi
  - direnv
  - bitwarden-cli

## Assumptions

- There is an available subnet you can use for this new SysEnv, some recommendations are below:
  - [Obtain Non-Overlapping IP Address Block](https://getstarted.awsworkshop.io/01-up-front-tasks/04-address-prereqs/03-obtain-ip-address-range.html)
  - [Recommended IP address range size](https://getstarted.awsworkshop.io/01-up-front-tasks/04-address-prereqs/03-obtain-ip-address-range.html#recommended-ip-address-range-size)
    - `/16`
- You cloned the following repositories to your local environment
  - <https://github.com/Over-haul/cloud-accounts-tools>
  - <https://github.com/Over-haul/infra-thunder-public>
- You are familiar with infra-thunder topics - seen [here](https://github.com/Over-haul/infra-thunder-public#topics)

## Creating a new SysEnv

This process is broken into 2 big parts.

1. Create a new AWS sub-account, this is only necessary when there is no
   existing AWS account with the same phase and purpose as the SysEnv you want
   to create
   - Example:
     - You currently have 2 SysEnvs:
       - oh-aws-us-east-1-app-prod
       - oh-aws-us-east-1-tools-prod
     - You want to create 2 new Sysenvs:
       - oh-aws-us-west-2-app-prod
       - oh-aws-us-west-2-app-dev
     - In the case of oh-aws-us-west-2-app-prod you would use the same AWS
       account as oh-aws-us-east-1-app-prod
     - In the case of oh-aws-us-west-2-app-dev you would create a new AWS
       account

2. Create pulumi stacks in this account (vpc, ssm, k8s-controllers, k8s-agents, pritunl, etc)

## Create new AWS sub-account

- Make sure you have valid administrator credentials for your primary AWS
  account.
  Example: login with SSO via `saml2aws`

  ```shell
  saml2aws login -a <primary account alias>
  ```

- Download `Federation Metadata XML` from your Identity Provider (IdP), like Google Apps, Azure AD, etc
- Make sure you have [poetry](https://python-poetry.org/) installed
- `cd` into <https://github.com/Over-haul/cloud-accounts-tools>
- run `setup_account.py` with the parameters for the new sysenv, example below:

```shell
AWS_PROFILE=<primary account alias> poetry run python setup_account.py -a oh-aws-app-dev \
 -f path/to/Fedration_Metadata.xml -s azuread -c dev -p app -r us-west-2 \
 -e infeng+oh-aws-app-dev@example.com -t oh
```

- Create the new App Roles in your IdP for the new sub-account
- If you use `saml2aws`, add the new role and account alias to your
  `~/.saml2aws` config file.
- Recover the root password for the new account
  - Go to [https://console.aws.amazon.com/console/home](https://console.aws.amazon.com/console/home)
  - Enter the email address you used to create the account above.
    Example: <infeng+oh-aws-app-dev@example.com>
  - Click "Forgot password"
  - An email will be sent to the email address to allow password reset
  - Reset the password and save this new username and password in your secrets
    manager (LastPass, Bitwarden, 1Password, etc)
  - Login as the new root account and then enable MFA and store the private key
    in in your secrets manager (LastPass, Bitwarden, 1Password, etc)

## Create pulumi stacks

- Make sure you have python 3.9+ installed
  - with virtualenv or venv
- Create a new passphrase to be used to encrypt secrets in the new pulumi
  SysEnv and save it in your secrets manager (LastPass, Bitwarden, 1Password,
  etc)
- Create a new Datadog API Key specific to this SysEnv
  - **Note:** It is important to create the new Datadog API Key and App Key as
    a [service account](https://docs.datadoghq.com/account_management/org_settings/service_accounts/)
- `cd` into <https://github.com/Over-haul/infra-thunder-public>
- `cd` into `sysenvs/aws`
- Create a new folder named after the SysEnv you want to create, Example: oh-aws-us-west-2-app-dev
  - To avoid writing a lot of boilerplate code we recommend you copy from an existing folder
  - Example: `cp -r oh-aws-us-east-1-app-dev oh-aws-us-west-2-app-dev`
- Add the folder to git
  - Example: `git add oh-aws-us-west-2-app-dev`
- `cd` into newly created SysEnv folder
  - Example: `cd oh-aws-us-west-2-app-dev`
  - Thanks to `direnv` the following environment variables will be set
  - `PULUMI_CONFIG_PASSPHRASE` # Pulled from bitarden via the `bw` cli
  - `AWS_PROFILE`
- Replace all instances of the previous SysEnv in this new folder you created
  - An easy way to do this is to use a bash function like `gitgrepreplace` from missingcharacter's `dot-files`
    - [BSD sed version is here](https://github.com/missingcharacter/dot-files/blob/a21c0d657236e2ebc7c5972a2d517e736be26cb5/MacOS/bash_aliases#L51-L57)
    - [GNU sed version is here](https://github.com/missingcharacter/dot-files/blob/a21c0d657236e2ebc7c5972a2d517e736be26cb5/Ubuntu/bash_aliases#L77-L83)
  - Example:

    ```shell
    gitgreprelace 'oh-aws-us-east-1-app-dev' 'oh-aws-us-west-2-app-dev'
    ```

- Generate a new encryption salt and replace it in all stack files
  - The encryption salt is the first line in a stack file

    ```shell
    $ grep 'encryptionsalt' stacks/Pulumi.vpc.yaml
    encryptionsalt: <REDACTED>
    ```

  - Remove the encryption salt from the `vpc` stack
    - BSD sed: `sed -i '' '/encryptionsalt/d' stacks/Pulumi.vpc.yaml`
    - GNU sed: `sed -i '/encryptionsalt/d' stacks/Pulumi.vpc.yaml`

  - Create the `vpc` stack with pulumi

    ```shell
    $ pulumi stack select
    Please choose a stack, or create a new one:
    > <create a new stack>
    Please enter your desired stack name: vpc
    Created stack 'vpc'
    ```

    - This step will add the `encryptionsalt` line at the beginning
      of `stacks/Pulumi.vpc.yaml`, and will also re-order the contents of it.
  - Copy the `encryptionsalt` line from `stacks/Pulumi.vpc.yaml`

    ```shell
    grep 'encryptionsalt' stacks/Pulumi.vpc.yaml
    encryptionsalt: <REDACTED>
    ```

  - if you don't like how pulumi re-ordered the file, restore the vpc stack
    file back to the way it was before pulumi re-ordered the file:

    ```shell
    git checkout -- stacks/Pulumi.vpc.yaml
    ```

  - Replace the previous encryptionsalt line with the new one

    ```shell
    $ gitgreprelace 'encryptionsalt: <OLD-REDACTED>' \
      'encryptionsalt: <NEW-REDACTED>'
    ```

- If the SysEnv you are about to create is in a different region than the one
  you copied from, replace the instances of the old region with the new region,
  example below:

  ```shell
  gitgrepreplace 'us-east-1' 'us-west-2'
  ```

- Remember to update `Thunder.common.yaml`

  ```shell
  sysenv: # Override this SysEnv name
  phase: # The phase of this SysEnv (prod, dev, stage, ...)
  purpose: # The purpose of this SysEnv (app, data, tools, ...)
  team: # Who's responsible for any resources created by Thunder in this SysEnv?
  prompt\_color: # For any resources that allow SSH access, what should the shell prompt color be?
  ```

- Update IP address space in all CIDRs
  - You can use `gitgrepreplace`, example when changing from one `/16` to
    another `/16`:

    ```shell
    gitgrepreplace '10.X' '10.Y'
    ```

- Create the resources declared in the `vpc` stack
  - Confirm the values and name match what you would expect

    ```shell
    pulumi preview --diff
    ```

  - Run `pulumi up`
- Create `ssm` stack

  ```shell
  $ pulumi stack select
  Please choose a stack, or create a new one:
  vpc
  > <create a new stack>
  Please enter your desired stack name: ssm
  Created stack 'ssm'
  ```

- Overwrite the `DD_API_KEY` and `DD_APP_KEY` values in the ssm stack with the
  one you just created for this SysEnv

  ```shell
  $ pulumi config set --secret --path 'ssm:parameters.DD_API_KEY'
  value:
  $ pulumi config set --secret --path 'ssm:parameters.DD_APP_KEY'
  value:
  ```

  - You can confirm the value is correct running `pulumi config --show-secrets`

    ```shell
    $ pulumi config --show-secrets
    KEY VALUE
    aws:region us-west-2
    ssm:parameters {"DD_API_KEY":"<REDACTED>"}
    ```

- Review, replace and delete parameters in `stacks/Pulumi.ssm.yaml`
- Create the resources declared in the `ssm` stack
  - Confirm the values and name match what you would expect

    ```shell
    pulumi preview --diff
    ```

  - Run `pulumi up`
- Create `datadog-integration` stack

  ```shell
  $ pulumi stack select
  Please choose a stack, or create a new one:
  ssm
  vpc
  > <create a new stack>
  Please enter your desired stack name: datadog-integration
  Created stack 'datadog-integration'
  ```

- Create the resources declared in the `datadog-integration` stack by
  running `pulumi up`
- Create `k8s-controllers` stack

  ```shell
  $ pulumi stack select
  Please choose a stack, or create a new one:
  ssm
  vpc
  datadog-integration
  > <create a new stack>
  Please enter your desired stack name: k8s-controllers
  Created stack 'k8s-controllers'
  ```

- Create the resources declared in the `k8s-controllers` stack by
  running `pulumi up`
- Create `k8s-agents` stack

  ```shell
  $ pulumi stack select
  Please choose a stack, or create a new one:
  datadog-integration
  k8s-controllers
  ssm
  vpc
  > <create a new stack>
  Please enter your desired stack name: k8s-agents
  Created stack 'k8s-agents'
  ```

- Create the resources declared in the `k8s-agents` stack by
  running `pulumi up`
- We are mostly done, you may want to add postgresql, opensearch, sqs or more,
  the process is very similar to what you've seen above
