import pulumi_datadog as datadog
from pulumi import ResourceOptions, Output
from pulumi_aws import cloudformation, iam, ssm, secretsmanager

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.config import get_stack
from infra_thunder.lib.ssm import PARAMETER_STORE_COMMON
from .config import DatadogConfig, DatadogExports


class DatadogIntegration(AWSModule):
    def __init__(self, name: str, config: DatadogConfig, opts: ResourceOptions = None):
        super().__init__(name, config, opts)

        self.datadog_provider = None
        self.datadog_api_key = None
        self.datadog_app_key = None
        self.datadog_api_url = None
        self.datadog_site = None
        self.iam_role_name = "DatadogAWSIntegrationRole"
        self.function_name = "datadog-forwarder"
        self.stream_name = "datadog-metrics-stream"
        self.datadog_aws_account_id = "464622532012"

    def build(self, config: DatadogConfig) -> DatadogExports:
        if config.api_key:
            self.datadog_api_key = config.api_key
        else:
            self.datadog_api_key = Output.secret(
                ssm.get_parameter(f"{PARAMETER_STORE_COMMON}/DD_API_KEY", with_decryption=True).value
            )
        if config.app_key:
            self.datadog_app_key = config.app_key
        else:
            self.datadog_app_key = Output.secret(
                ssm.get_parameter(f"{PARAMETER_STORE_COMMON}/DD_APP_KEY", with_decryption=True).value
            )
        if config.datadog_site:
            self.datadog_site = config.datadog_site
        else:
            self.datadog_site = Output.secret(
                ssm.get_parameter(f"{PARAMETER_STORE_COMMON}/DD_SITE", with_decryption=True).value
            )
        self.datadog_api_url = Output.concat("https://api.", self.datadog_site, "/")

        self.datadog_provider = datadog.Provider(
            "dd",
            api_key=self.datadog_api_key,
            app_key=self.datadog_app_key,
            api_url=self.datadog_api_url,
            opts=ResourceOptions(parent=self),
        )

        integration = datadog.aws.Integration(
            get_stack(),
            account_id=self.aws_account_id,
            role_name=self.iam_role_name,
            opts=ResourceOptions(
                parent=self.datadog_provider,
                provider=self.datadog_provider,
                delete_before_replace=True,
            ),
        )
        datadog_assume_role = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{self.datadog_aws_account_id}:root"},
                    "Condition": {"StringEquals": {"sts:ExternalId": integration.external_id}},
                }
            ],
        }
        role = iam.Role(
            self.iam_role_name,
            name=self.iam_role_name,
            description="Thunder-generated role for Datadog integration",
            assume_role_policy=datadog_assume_role,
            opts=ResourceOptions(parent=integration),
        )
        integration_policy_name = "DatadogAWSIntegrationPolicy"
        iam.RolePolicy(
            integration_policy_name,
            name=integration_policy_name,
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Action": [
                            "apigateway:GET",
                            "autoscaling:Describe*",
                            "backup:List*",
                            "budgets:ViewBudget",
                            "cloudfront:GetDistributionConfig",
                            "cloudfront:ListDistributions",
                            "cloudtrail:DescribeTrails",
                            "cloudtrail:GetTrailStatus",
                            "cloudtrail:LookupEvents",
                            "cloudwatch:Describe*",
                            "cloudwatch:Get*",
                            "cloudwatch:List*",
                            "codedeploy:List*",
                            "codedeploy:BatchGet*",
                            "directconnect:Describe*",
                            "dynamodb:List*",
                            "dynamodb:Describe*",
                            "ec2:Describe*",
                            "ecs:Describe*",
                            "ecs:List*",
                            "elasticache:Describe*",
                            "elasticache:List*",
                            "elasticfilesystem:DescribeFileSystems",
                            "elasticfilesystem:DescribeTags",
                            "elasticfilesystem:DescribeAccessPoints",
                            "elasticloadbalancing:Describe*",
                            "elasticmapreduce:List*",
                            "elasticmapreduce:Describe*",
                            "es:ListTags",
                            "es:ListDomainNames",
                            "es:DescribeElasticsearchDomains",
                            "events:CreateEventBus",
                            "fsx:DescribeFileSystems",
                            "fsx:ListTagsForResource",
                            "health:DescribeEvents",
                            "health:DescribeEventDetails",
                            "health:DescribeAffectedEntities",
                            "kinesis:List*",
                            "kinesis:Describe*",
                            "lambda:GetPolicy",
                            "lambda:List*",
                            "logs:DeleteSubscriptionFilter",
                            "logs:DescribeLogGroups",
                            "logs:DescribeLogStreams",
                            "logs:DescribeSubscriptionFilters",
                            "logs:FilterLogEvents",
                            "logs:PutSubscriptionFilter",
                            "logs:TestMetricFilter",
                            "organizations:Describe*",
                            "organizations:List*",
                            "rds:Describe*",
                            "rds:List*",
                            "redshift:DescribeClusters",
                            "redshift:DescribeLoggingStatus",
                            "route53:List*",
                            "s3:GetBucketLogging",
                            "s3:GetBucketLocation",
                            "s3:GetBucketNotification",
                            "s3:GetBucketTagging",
                            "s3:ListAllMyBuckets",
                            "s3:PutBucketNotification",
                            "ses:Get*",
                            "sns:List*",
                            "sns:Publish",
                            "sqs:ListQueues",
                            "states:ListStateMachines",
                            "states:DescribeStateMachine",
                            "support:DescribeTrustedAdvisor*",
                            "support:RefreshTrustedAdvisorCheck",
                            "tag:GetResources",
                            "tag:GetTagKeys",
                            "tag:GetTagValues",
                            "xray:BatchGetTraces",
                            "xray:GetTraceSummaries",
                        ],
                        "Effect": "Allow",
                        "Resource": "*",
                    },
                ]
            },
            opts=ResourceOptions(parent=role),
        )
        resource_collection_policy_name = "DatadogAWSResourceCollectionPolicy"
        iam.RolePolicy(
            resource_collection_policy_name,
            name=resource_collection_policy_name,
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "acm:DescribeCertificate",
                            "acm:ListCertificates",
                            "backup:ListBackupPlans",
                            "backup:ListBackupVaults",
                            "cloudfront:GetDistribution",
                            "cloudfront:ListDistributions",
                            "cloudtrail:DescribeTrails",
                            "cloudtrail:GetEventSelectors",
                            "cloudtrail:GetTrailStatus",
                            "config:DescribeConfigurationRecorderStatus",
                            "config:DescribeConfigurationRecorders",
                            "iam:GenerateCredentialReport",
                            "iam:GetAccountPasswordPolicy",
                            "iam:GetAccountSummary",
                            "iam:GetCredentialReport",
                            "iam:GetLoginProfile",
                            "iam:GetPolicyVersion",
                            "iam:ListAttachedUserPolicies",
                            "iam:ListEntitiesForPolicy",
                            "iam:ListMFADevices",
                            "iam:ListPolicies",
                            "iam:ListRoles",
                            "iam:ListServerCertificates",
                            "iam:ListUserPolicies",
                            "iam:ListUsers",
                            "iam:ListVirtualMFADevices",
                            "kms:GetKeyPolicy",
                            "kms:GetKeyRotationStatus",
                            "kms:ListAliases",
                            "kms:ListKeys",
                            "lambda:GetPolicy",
                            "lambda:ListFunctions",
                            "redshift:DescribeClusterParameterGroups",
                            "redshift:DescribeClusterParameters",
                            "redshift:DescribeLoggingStatus",
                            "rds:DescribeDBSecurityGroups",
                            "rds:DescribeDBSnapshotAttributes",
                            "rds:DescribeDBSnapshots",
                            "s3:GetBucketAcl",
                            "s3:GetBucketLogging",
                            "s3:GetBucketPolicy",
                            "s3:GetBucketPolicyStatus",
                            "s3:GetBucketPublicAccessBlock",
                            "s3:GetBucketVersioning",
                            "s3:GetEncryptionConfiguration",
                            "sns:GetSubscriptionAttributes",
                            "sns:GetTopicAttributes",
                            "sns:ListSubscriptions",
                            "sns:ListTopics",
                            "sqs:GetQueueAttributes",
                            "sqs:ListQueues",
                        ],
                        "Resource": "*",
                    },
                ]
            },
            opts=ResourceOptions(parent=role),
        )
        iam.RolePolicyAttachment(
            "SecurityAuditAttachment",
            role=role.name,
            policy_arn="arn:aws:iam::aws:policy/SecurityAudit",
            opts=ResourceOptions(parent=role),
        )
        # Setting up Datadog Serverless functions
        dd_api_key_secret = secretsmanager.Secret(
            "datadog_api_key",
            description="Encrypted Datadog API Key",
            opts=ResourceOptions(parent=self),
        )
        dd_api_key_secret_version = secretsmanager.SecretVersion(
            "datadog_api_key_version",
            secret_id=dd_api_key_secret.id,
            secret_string=self.datadog_api_key,
            opts=ResourceOptions(parent=dd_api_key_secret),
        )
        cloudformation.Stack(
            self.function_name,
            name=self.function_name,
            capabilities=[
                "CAPABILITY_IAM",
                "CAPABILITY_NAMED_IAM",
                "CAPABILITY_AUTO_EXPAND",
            ],
            parameters={
                "DdApiKeySecretArn": dd_api_key_secret_version.arn,
                "FunctionName": self.function_name,
                "DdSite": self.datadog_site,
            },
            template_url=f"https://datadog-cloudformation-template.s3.amazonaws.com/aws/forwarder/{config.forwarder_version}.yaml",
            opts=ResourceOptions(parent=dd_api_key_secret_version),
        )
        cloudformation.Stack(
            self.stream_name,
            name=self.stream_name,
            capabilities=[
                "CAPABILITY_NAMED_IAM",
            ],
            parameters={
                "ApiKey": self.datadog_api_key,
                "Regions": ",".join([self.region] + config.extra_regions),
                "DdSite": self.datadog_site,
            },
            template_url="https://datadog-cloudformation-stream-template.s3.amazonaws.com/aws/streams_main.yaml",
            opts=ResourceOptions(parent=integration, ignore_changes=["parameters"]),
        )
        return DatadogExports(
            external_id=integration.external_id,
            id=integration.id,
        )
