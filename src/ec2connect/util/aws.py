"""aws utility class"""

# Copyright 2023 Goodwill of Central and Northern Arizona
#
# Licensed under the BSD 3-Clause (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://opensource.org/licenses/BSD-3-Clause
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import re
import shutil
from functools import update_wrapper
from pathlib import Path
from subprocess import run, CalledProcessError
from typing import Callable, Any

import boto3
from click import UsageError, pass_context, echo
from questionary import Choice
from packaging import version

logger = logging.getLogger("ec2connect.aws")

__MIN_AWS_VERSION__ = "2.12.0"


def validate_aws_cli(f) -> Callable:
    """

    Args:
        f: function being wrapped

    Returns: Callable

    """

    @pass_context
    def wrapper(ctx, *args, **kwargs):
        aws_version_string = run(
            [_find_aws_cli(), "--version"], capture_output=True, check=True, text=True
        )
        aws_version = _extract_aws_version(aws_version_string.stdout)

        if version.parse(aws_version) < version.parse(__MIN_AWS_VERSION__):
            raise UsageError(
                f"aws cli version must be at least version {__MIN_AWS_VERSION__}, please upgrade."
            )

        return ctx.invoke(f, *args, **kwargs)

    return update_wrapper(wrapper, f)


def instance_choices(profile: str, region: str, public_only: bool = False) -> list[Choice]:
    """

    Args:
        profile:
        region:
        public_only: If only public instances should be enabled choices

    Returns: list[Choice]

    """
    ec2 = boto3.Session(profile_name=profile).client("ec2", region_name=region)
    response = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
        MaxResults=1000,
    )

    choices = list(map(_create_choice(public_only), list(response["Reservations"])))
    return choices


def instance_connect(  # pylint: disable=too-many-arguments
    profile: str,
    region: str,
    instance_id: str,
    os_user: str = "ec2-user",
    ssh_port: str = "22",
    private_key_file: str | None = None,
    debug: bool = False,
) -> None:
    """

    Args:
        profile: AWS profile to use
        region: AWS region to use
        instance_id: AWS Instance ID to connect to
        os_user: OS User to log in as, defaults to ec2-user
        ssh_port: Port on instance to SSH to, defaults to 22
        private_key_file: Private key file to use, default None
        debug: debug flag for AWS command
    """
    args = [
        _find_aws_cli(),
        "--profile",
        profile,
        "--region",
        region,
        "ec2-instance-connect",
        "ssh",
        "--instance-id",
        instance_id,
        "--connection-type",
        "eice",
        "--os-user",
        os_user,
        "--ssh-port",
        ssh_port,
    ]

    if private_key_file:
        args.extend(["--private-key-file", private_key_file])

    if debug:
        args.append("--debug")

    os.execvp(args[0], args)


def instance_connect_key(  # pylint: disable=too-many-arguments
    profile: str,
    region: str,
    instances: Any,
    private_key_file: Path,
    os_user: str = "ec2-user",
    debug: bool = False,
) -> None:
    """

    Args:
        profile:
        region:
        instances: List of instances to push public key to
        private_key_file: Private key path to get public key from
        os_user: OS User to push with request, defaults to ec2-user
        debug:

    Returns: None

    """
    _create_ssh_keypair(private_key_file, debug)

    instances = [instances] if not isinstance(instances, list) else instances

    public_dns = None
    private_dns = None
    for instance in instances:
        args = [
            _find_aws_cli(),
            "--profile",
            profile,
            "--region",
            region,
            "ec2-instance-connect",
            "send-ssh-public-key",
            "--instance-id",
            instance["instance_id"],
            "--instance-os-user",
            os_user,
            "--ssh-public-key",
            private_key_file.with_suffix(".pub").as_uri(),
        ]

        if debug:
            args.append("--debug")

        run(args, check=True, capture_output=True)

        # Set some variables, so we can construct some sample SCP or SSH commands
        if instance["public_dns"]:
            public_dns = public_dns or instance["public_dns"]
        else:
            private_dns = private_dns or instance["private_dns"]

        hostname = instance["public_dns"] or instance["private_dns"]
        echo(f"You have 60 seconds to log in to {hostname} with {private_key_file}")

    # Remove the public key so ssh-agent doesn't get bloated
    try:
        os.remove(private_key_file.with_suffix(".pub"))
    except FileNotFoundError:
        pass

    # Print out some example commands if we have a hostnames
    if not public_dns or not private_dns:
        return

    proxy_command = f"ssh -i {private_key_file} -W '[%h]:%p' {os_user}@{public_dns}"
    ssh_command = f'ssh -o ProxyCommand="{proxy_command}" -i {private_key_file} {os_user}@{private_dns}'
    scp_command = f'scp -o ProxyCommand="{proxy_command}" -i {private_key_file} <file> {os_user}@{private_dns}:<file>'

    echo(f"Example SSH command:\n{ssh_command}")
    echo(f"Example SCP command:\n{scp_command}")


def _find_aws_cli() -> str:
    aws = shutil.which("aws")
    if aws is None:
        raise UsageError("aws cli could not be found on PATH")
    return aws


def _extract_aws_version(version_string: str) -> str:
    return re.match(r"^aws-cli/(.*?) ", version_string).group(1)


def _create_choice(public_only: bool):
    def _inner_create_choice(instances) -> Choice:
        # Find a name tag
        instance = instances["Instances"][0]
        tags = [tag for tag in instance["Tags"] if tag["Key"] == "Name"]

        return Choice(
            title=instance["InstanceId"]
            + (" (" + tags[0]["Value"] + ")" if len(tags) == 1 else ""),
            value={
                "instance_id": instance["InstanceId"],
                "public_dns": instance["PublicDnsName"] or None,
                "private_dns": instance["PrivateDnsName"],
            },
            disabled="No public DNS"
            if public_only and not instance["PublicDnsName"]
            else None,
        )

    return _inner_create_choice


def _create_ssh_keypair(private_key_file: Path, debug: bool = False):
    try:
        os.remove(private_key_file)
    except FileNotFoundError:
        pass

    try:
        args = [
            _find_ssh_keygen(),
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "ec2connect@auto",
            "-f",
            private_key_file,
        ]

        if debug:
            args.append("-v")

        run(
            args,
            check=True,
            capture_output=True,
        )
    except CalledProcessError as error:
        raise UsageError(f"Error generating SSH key: {error.output}") from error


def _find_ssh_keygen() -> str:
    ssh_keygen = shutil.which("ssh-keygen")
    if ssh_keygen is None:
        raise UsageError(
            "ssh-keygen could not be found on PATH, is openssh-client installed?"
        )
    return ssh_keygen
