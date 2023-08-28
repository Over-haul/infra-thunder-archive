from pulumi import Output, ResourceOptions, get_stack
from pulumi_aws import s3 as aws_s3
from pulumi_aws.organizations.get_organization import get_organization
from pulumi_aws.s3 import BucketVersioningArgs

from infra_thunder.lib.aws.base import AWSModule
from infra_thunder.lib.s3 import generate_bucket_name
from infra_thunder.lib.tags import get_tags
from .config import S3Args, S3Exports


class S3Bucket(AWSModule):
    def build(self, config: S3Args) -> list[S3Exports]:
        return [self._create_bucket(bucket.name, bucket.acl, bucket.versioning) for bucket in config.buckets]

    def _create_bucket(self, name: str, acl: str, versioning: bool) -> S3Exports:
        bucket_hash_name = generate_bucket_name(name)

        bucket = aws_s3.Bucket(
            bucket_hash_name,
            bucket=bucket_hash_name,
            acl=acl,
            versioning=BucketVersioningArgs(enabled=versioning),
            tags=get_tags(get_stack(), "bucket", name),
            opts=ResourceOptions(ignore_changes=["lifecycleRules", "replicationConfiguration"]),
        )
        bucket_public_access_block = aws_s3.BucketPublicAccessBlock(
            bucket_hash_name,
            bucket=bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=ResourceOptions(parent=bucket),
        )

        aws_s3.BucketPolicy(
            f"{bucket_hash_name}-org-only-policy",
            bucket=bucket.id,
            policy={
                "Version": "2012-10-17",
                "Id": f"{bucket_hash_name}-Policy",
                "Statement": [
                    {
                        "Sid": f"{bucket_hash_name}-DenyEverythingExceptOrg",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "*:*",
                        "Resource": [
                            Output.concat(bucket.arn),
                            Output.concat(bucket.arn, "/*"),
                        ],
                        "Condition": {"StringNotEquals": {"aws:PrincipalOrgID": get_organization().id}},
                    }
                ],
            },
            opts=ResourceOptions(parent=bucket_public_access_block),
        )

        return S3Exports(
            bucket=bucket.bucket,
            bucket_domain_name=bucket.bucket_domain_name,
            friendly_name=name,
            region=bucket.region,
        )
