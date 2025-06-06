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
import socket
from contextlib import closing
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
    response = get_instances(profile, region)

    return list(map(_create_choice(public_only), response))


def get_instances(profile, region):
    """
    Args:
        profile:
        region:

    Returns: list[dict]

    """
    ec2 = boto3.Session(profile_name=profile).client("ec2", region_name=region)
    response = ec2.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
        MaxResults=1000,
    )
    return list(response["Reservations"])


def get_instance(profile, region, instance_id):
    """
    Args:
        profile:
        region:
        instance_id:

    Returns:

    """
    instances = get_instances(profile, region)
    for instance in instances:
        if instance["Instances"][0]["InstanceId"] == instance_id:
            return {
                "instance_id": instance["Instances"][0]["InstanceId"],
                "public_dns": instance["Instances"][0]["PublicDnsName"] or None,
                "private_dns": instance["Instances"][0]["PrivateDnsName"],
            }

    return None


def instance_connect(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    profile: str,
    region: str,
    instance: Any,
    os_user: str = "ec2-user",
    ssh_port: str = "22",
    private_key_file: str | None = None,
    debug: bool = False,
) -> None:
    """

    Args:
        profile: AWS profile to use
        region: AWS region to use
        instance: AWS Instance ID to connect to
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
        instance["instance_id"],
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


def instance_connect_key(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    profile: str,
    region: str,
    instances: Any,
    private_key_file: Path | str,
    os_user: str = "ec2-user",
    no_output: bool = False,
    debug: bool = False,
) -> None:
    """

    Args:
        profile:
        region:
        instances: List of instances to push public key to
        private_key_file: Private key path to get public key from
        os_user: OS User to push with request, defaults to ec2-user
        no_output: Do not print
        debug:

    Returns: None

    """
    private_key_file = Path(private_key_file)
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
        if not no_output:
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

    if not no_output:
        echo(f"Example SSH command:\n{ssh_command}")
        echo(f"Example SCP command:\n{scp_command}")


def tunnel(  # pylint: disable=too-many-arguments,too-many-locals,consider-using-with,too-many-positional-arguments
        profile: str,
        region: str,
        instance: Any,
        remote_port: str,
        endpoint: str,
        local_port: str | None = None,
        os_user: str = "ec2-user",
        private_key_file: str | None = None,
        debug: bool = False,
) -> None:
    """
    Create local SSH tunnel using ec2 instance connect open-tunnel
    Args:
        profile:
        region:
        instance:
        remote_port:
        endpoint:
        local_port:
        os_user:
        ssh_port:
        private_key_file:
        debug:

    Returns:

    """
    local_port = _find_free_port() if local_port is None else local_port

    # Start a tunnel first
    tunnel_args = [
        _find_aws_cli(),
        "--profile",
        profile,
        "--region",
        region,
        "ec2-instance-connect",
        "open-tunnel",
        "--instance-id",
        instance["instance_id"]
    ]

    if debug:
        tunnel_args.append("--debug")

    # Put a key onto the instance next so we can tunnel into it
    instance_connect_key(
        profile=profile,
        region=region,
        instances=instance,
        private_key_file=private_key_file,
        os_user=os_user,
        debug=debug,
        no_output=True
    )

    ssh_args = [
        _find_ssh(),
        "-NL",
        f"127.0.0.1:{local_port}:{endpoint}:{remote_port}",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        f"ProxyCommand={' '.join(tunnel_args)}",
        "-o",
        "LogLevel=ERROR",
        "-l",
        os_user,
        "-i",
        private_key_file
    ]

    if debug:
        ssh_args.append("-v")

    ssh_args.append("127.0.0.1")

    echo(f"Opening tunnel to {endpoint}:{remote_port} open on 127.0.0.1:{local_port}")

    os.execvp(ssh_args[0], ssh_args)


def _find_aws_cli() -> str:
    aws = shutil.which("aws")
    if aws is None:
        raise UsageError("aws cli could not be found on PATH")
    return aws


def _find_ssh() -> str:
    ssh = shutil.which("ssh")
    if ssh is None:
        raise UsageError("ssh could not be found on PATH")
    return ssh


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


def _find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return str(s.getsockname()[1])
