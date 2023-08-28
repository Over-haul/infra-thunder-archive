import logging
import os
from operator import itemgetter

import boto3
import click
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup

ec2 = boto3.client("ec2")
autoscaling = boto3.client("autoscaling")


def echo_key_value(key, value):
    click.echo(click.style(f"{key}: ", fg="green", bold=True) + str(value))


@click.group()
@click.option("--debug", is_flag=True, default=False, help="Enable DEBUG logging")
def cli(debug):
    if "AWS_PROFILE" not in os.environ:
        raise Exception("`AWS_PROFILE` is not set")

    logging.basicConfig(format="[%(asctime)s %(levelname)s %(name)s %(threadName)s]: %(message)s")

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        click.echo("Enabled debug mode!")


@cli.command()
@optgroup.group(
    "Identifiers",
    cls=RequiredMutuallyExclusiveOptionGroup,
    help="The manner of identifying the instance",
)
@optgroup.option("--id", help="Instance ID")
@optgroup.option("--ip", help="Instance Internal IP Address")
@click.option(
    "--replace",
    help="Launch instance to replace the one that is terminated",
    is_flag=True,
)
@click.option(
    "-y",
    "--yes",
    help="Answer yes to all questions",
    is_flag=True,
)
def terminate_instance(id, ip, replace, yes):
    instance_id = id
    ip_address = ip

    click.echo()

    if ip_address:
        filters = [
            {
                "Name": "private-ip-address",
                "Values": [ip_address],
            }
        ]

        ec2_response = ec2.describe_instances(Filters=filters)

        instance_list = ec2_response["Reservations"][0]["Instances"]

        if len(instance_list) != 1:
            raise Exception("No instance with that IP address was found")

        instance_id = instance_list[0]["InstanceId"]

    elif instance_id:
        filters = [
            {
                "Name": "instance-id",
                "Values": [instance_id],
            }
        ]

        ec2_response = ec2.describe_instances(Filters=filters)

        try:
            instance_list = ec2_response["Reservations"][0]["Instances"]
            ip_address = instance_list[0]["PrivateIpAddress"]
        except Exception:
            click.echo("WARNING: EC2 API found no instance with that Instance ID")

    echo_key_value("Instance ID", instance_id)
    echo_key_value("IP Address", ip_address)

    response = autoscaling.describe_auto_scaling_instances(
        InstanceIds=[instance_id],
    )

    instance_descriptions = response["AutoScalingInstances"]

    if not len(instance_descriptions):
        raise Exception("No instance with that instance ID was found")

    instance_description = instance_descriptions[0]
    instance_type, availability_zone, asg_name = itemgetter("InstanceType", "AvailabilityZone", "AutoScalingGroupName")(
        instance_description
    )

    echo_key_value("Instance Type", instance_type)
    echo_key_value("Availability Zone", availability_zone)
    echo_key_value("Auto Scaling Group Name", asg_name)

    asg_descriptions = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name],
    )
    asg_description = asg_descriptions["AutoScalingGroups"][0]

    min_size, max_size, desired_capacity = itemgetter("MinSize", "MaxSize", "DesiredCapacity")(asg_description)

    echo_key_value("Min Size", min_size)
    echo_key_value("Max Size", max_size)
    echo_key_value("Desired Capacity", desired_capacity)

    click.echo()

    if yes or click.confirm("Do you want to continue?"):
        click.echo()

        decrement_capacity = not replace

        response = autoscaling.terminate_instance_in_auto_scaling_group(
            InstanceId=instance_id,
            ShouldDecrementDesiredCapacity=decrement_capacity,
        )["Activity"]

        description, cause, status_code = itemgetter("Description", "Cause", "StatusCode")(response)

        echo_key_value("Description", description)
        echo_key_value("Cause", cause)
        echo_key_value("Status Code", status_code)


def run():
    exit(cli())


if __name__ == "__main__":
    run()
