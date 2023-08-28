---
parent: AWS Modules
---

# Assumable IAM Roles

Thunder allows operators to easily create roles that can be assumed by Kubernetes Pods or individual instances that
require scoped access to IAM-controlled resources.

## Sub-topics

- [Cross-Account Access](#cross-account-access)

## Provides

- Individual IAM roles in the `service/` scope that can be assumed by tools like [Kube2IAM](../k8s/controllers/README.md#kube2iam)
- Role interpolation function to allow operators to specify AWS ARNs that automatically detect the appropriate AWS partition and Account ID

## Caveats

- This module only creates IAM roles, and does not validate that the ARNs referenced in any policy are valid.  
  Operators must ensure the resource ARNs listed in any role exist before applying this module.

## Requirements

- ARNs should exist before referencing them in this module

## Configuration and Outputs

[Please check the config dataclass for configuration options, outputs, and documentation]({{ site.aux_links.Github[0] }}/{{ page.dir }}config.py)

Sample `Pulumi.iam-roles.yaml`:

```yaml
config:
  aws:region: us-east-1

  iam-roles:roles:
    - name: jenkins-builder
      policies:
        - name: assume-parent-jenkins
          statements:
            - Effect: Allow
              Action:
                - 'sts:AssumeRole'
              Resource: ['arn:{partition}:iam::01234567891:role/jenkins']
        - name: packer
          statements:
            - Effect: Allow
              Action:
                - 'ec2:AttachVolume'
                - 'ec2:AuthorizeSecurityGroupIngress'
                - 'ec2:CopyImage'
                - 'ec2:CreateImage'
                - 'ec2:CreateKeypair'
                - 'ec2:CreateSecurityGroup'
                - 'ec2:CreateSnapshot'
                - 'ec2:CreateTags'
                - 'ec2:CreateVolume'
                - 'ec2:DeleteKeyPair'
                - 'ec2:DeleteSecurityGroup'
                - 'ec2:DeleteSnapshot'
                - 'ec2:DeleteVolume'
                - 'ec2:DeregisterImage'
                - 'ec2:DescribeImageAttribute'
                - 'ec2:DescribeImages'
                - 'ec2:DescribeInstances'
                - 'ec2:DescribeInstanceStatus'
                - 'ec2:DescribeRegions'
                - 'ec2:DescribeSecurityGroups'
                - 'ec2:DescribeSnapshots'
                - 'ec2:DescribeSubnets'
                - 'ec2:DescribeTags'
                - 'ec2:DescribeVolumes'
                - 'ec2:DetachVolume'
                - 'ec2:GetPasswordData'
                - 'ec2:ModifyImageAttribute'
                - 'ec2:ModifyInstanceAttribute'
                - 'ec2:ModifySnapshotAttribute'
                - 'ec2:RegisterImage'
                - 'ec2:RunInstances'
                - 'ec2:StopInstances'
                - 'ec2:TerminateInstances'
                - 'ec2:CreateLaunchTemplate'
                - 'ec2:DeleteLaunchTemplate'
                - 'ec2:CreateFleet'
                - 'ec2:DescribeSpotPriceHistory'
              Resource: ['*']

```

<!-- markdownlint-disable MD025 -->

# Topics

## Cross-Account Access

There may be use cases that require a Pod to assume a role that is present in another AWS Account. This can be
accomplished by:

1. Add a policy to a role created by this module like:

   ```yaml
   policies:
     - name: assume-parent-jenkins
       statements:
         - Effect: Allow
           Action:
             - 'sts:AssumeRole'
           Resource: ['arn:aws:iam::01234567891:role/jenkins']
   ```

2. Apply this module to the SysEnv to create the role, since you will need the role ARN for the next steps
3. Modify the **trust relationship** on the role you wish to assume, adding:

   ```json
   {
     "Sid": "",
     "Effect": "Allow",
     "Principal": {
       "AWS": [
         "**role ARN from above**"
       ]
     },
     "Action": "sts:AssumeRole"
   }
   ```

4. Create a ConfigMap for your Pod like:

   ```yaml
   kind: ConfigMap
   apiVersion: v1
   metadata:
     name: myapp-awsconfig
     namespace: mynamespace
   data:
     config: |
       [profile default]
       role_arn=arn:aws:iam::01234567890:role/my-role-123
       credential_source=Ec2InstanceMetadata
   ```

5. Modify the Pod configuration:

   ```yaml
   metadata:
     name: mypod
     annotations:
       iam.amazonaws.com/role: "**role ARN from above**"
       # if needed
       #iam.amazonaws.com/external-id: "external-id"
   spec:
     volumes:
       - name: aws-config
         configMap:
           name: myapp-awsconfig
           defaultMode: 420
      volumeMounts:
        - name: aws-config
          mountPath: /root/.aws/config
   ```
