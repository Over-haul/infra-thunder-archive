import hashlib

from pulumi import ResourceOptions
from pulumi_aws import iam


def generate_s3_policy(bucket: str, prefix: str = ""):
    """
    Generate an inline policy that allows the instance to read/write to a S3 bucket or path.

    NOTE: This policy is to be used to allow instances themselves access to a bucket, and is not suitable for pods.

    :param bucket: S3 bucket name
    :param prefix: Prefix to allow access to
    :return:
    """

    # Add `/*` if not present
    if not prefix.endswith("/*"):
        prefix = prefix + "/*"

    bucket_prefix_hash = hashlib.md5(f"{bucket}{prefix}".encode("utf-8")).hexdigest()

    def curried_generate_s3_policy(cls, role: iam.Role) -> iam.RolePolicy:
        """
        Curried (inner) function that returns the S3 policy

        :param cls: The calling class object
        :param role: The role to attach this policy to
        :return: iam.RolePolicy instance-policy
        """

        return iam.RolePolicy(
            f"s3-{bucket_prefix_hash[-5:]}",
            role=role.id,
            policy={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                            "s3:ListBucketMultipartUploads",
                            "s3:ListBucketVersions",
                        ],
                        "Resource": [f"arn:{cls.partition}:s3:::{bucket}"],
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:AbortMultipartUpload",
                            "s3:ListMultipartUploadParts",
                        ],
                        "Resource": [f"arn:{cls.partition}:s3:::{bucket}/{prefix}"],
                    },
                ]
            },
            opts=ResourceOptions(parent=role),
        )

    return curried_generate_s3_policy
