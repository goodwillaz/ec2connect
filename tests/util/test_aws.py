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

from pathlib import Path
from subprocess import CompletedProcess, CalledProcessError
from unittest import mock, TestCase

import click
import pytest
from questionary import Choice
from click.testing import CliRunner

from ec2connect.util.aws import (
    validate_aws_cli,
    __MIN_AWS_VERSION__,
    instance_choices,
    instance_connect,
    instance_connect_key,
)
from ec2connect.util.config import Config


pass_config = click.make_pass_decorator(Config, ensure=True)


class AwsTestCase(TestCase):
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_validate_aws_cli_good_version(self, mock_shutil, mock_run) -> None:
        mock_shutil.which.return_value = "aws"
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )

        @click.command()
        @pass_config
        @validate_aws_cli
        def foo(ctx):
            pass

        runner = CliRunner()
        result = runner.invoke(foo, standalone_mode=False)

        assert result.exit_code == 0
        assert not result.exception
        mock_run.assert_called_with(
            ["aws", "--version"], capture_output=True, check=True, text=True
        )

    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_validate_aws_cli_bad_version(self, mock_shutil, mock_run) -> None:
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.11 Python/3.11"
        )

        @click.command()
        @pass_config
        @validate_aws_cli
        def foo(ctx):
            pass

        runner = CliRunner()
        with pytest.raises(click.UsageError) as e:
            runner.invoke(foo, standalone_mode=False, catch_exceptions=False)

        assert (
            e.value.message
            == f"aws cli version must be at least version {__MIN_AWS_VERSION__}, please upgrade."
        )

    @mock.patch("ec2connect.util.aws.shutil")
    def test_validate_aws_cli_no_aws(self, mock_shutil) -> None:
        mock_shutil.which.return_value = None

        @click.command()
        @pass_config
        @validate_aws_cli
        def foo(ctx):
            pass

        runner = CliRunner()
        with pytest.raises(click.UsageError) as e:
            runner.invoke(foo, standalone_mode=False, catch_exceptions=False)

        assert e.value.message == "aws cli could not be found on PATH"

    @mock.patch("ec2connect.util.aws.boto3")
    def test_instance_choices_no_instances(self, mock_boto3):
        mock_boto3.Session.return_value.client.return_value.describe_instances.return_value = {
            "Reservations": []
        }

        result = instance_choices(profile="default", region="region")

        mock_boto3.Session.assert_called_with(profile_name="default")
        mock_boto3.Session.return_value.client.assert_called_with(
            "ec2", region_name="region"
        )

        assert result == []

    @mock.patch("ec2connect.util.aws.boto3")
    def test_instance_choices_one_instance(self, mock_boto3):
        mock_boto3.Session.return_value.client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "Tags": [{"Key": "Name", "Value": "Foo"}],
                            "InstanceId": "i-foo",
                            "PrivateDnsName": "private.foo.bar.baz",
                            "PublicDnsName": "public.foo.bar",
                        }
                    ]
                }
            ]
        }

        result = instance_choices(profile="default", region="region")

        assert len(result) == 1
        assert isinstance(result[0], Choice)
        assert result[0].disabled is None
        assert result[0].title == "i-foo (Foo)"
        assert result[0].value == {
            "instance_id": "i-foo",
            "public_dns": "public.foo.bar",
            "private_dns": "private.foo.bar.baz",
        }

    @mock.patch("ec2connect.util.aws.boto3")
    def test_instance_choices_no_public_dns(self, mock_boto3):
        mock_boto3.Session.return_value.client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "Tags": [{"Key": "Name", "Value": "Foo"}],
                            "InstanceId": "i-foo",
                            "PrivateDnsName": "private.foo.bar.baz",
                            "PublicDnsName": None,
                        }
                    ]
                }
            ]
        }

        result = instance_choices(profile="default", region="region")

        assert result[0].value == {
            "instance_id": "i-foo",
            "public_dns": None,
            "private_dns": "private.foo.bar.baz",
        }

    @mock.patch("ec2connect.util.aws.boto3")
    def test_instance_choices_no_name_tag(self, mock_boto3):
        mock_boto3.Session.return_value.client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "Tags": [],
                            "InstanceId": "i-foo",
                            "PrivateDnsName": "private.foo.bar.baz",
                            "PublicDnsName": None,
                        }
                    ]
                },
            ]
        }

        result = instance_choices(profile="default", region="region")

        assert result[0].title == "i-foo"

    @mock.patch("ec2connect.util.aws.boto3")
    def test_instance_choices_public_only(self, mock_boto3):
        mock_boto3.Session.return_value.client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "Tags": [],
                            "InstanceId": "i-foo",
                            "PrivateDnsName": "private.foo.bar.baz",
                            "PublicDnsName": None,
                        }
                    ]
                },
                {
                    "Instances": [
                        {
                            "Tags": [],
                            "InstanceId": "i-foo",
                            "PrivateDnsName": "private.foo.bar.baz",
                            "PublicDnsName": "public.foo.bar",
                        }
                    ]
                },
            ]
        }

        result = instance_choices(profile="default", region="region", public_only=True)

        assert result[0].disabled == "No public DNS"
        assert result[1].disabled is None

    @mock.patch("ec2connect.util.aws.shutil")
    @mock.patch("ec2connect.util.aws.os")
    def test_instance_connect_default_params(self, mock_os, mock_shutil):
        mock_shutil.which.return_value = "aws"

        instance_connect(profile="default", region="region", instance={"instance_id": "i-foo"})

        mock_os.execvp.assert_called_once_with(
            "aws",
            [
                "aws",
                "--profile",
                "default",
                "--region",
                "region",
                "ec2-instance-connect",
                "ssh",
                "--instance-id",
                "i-foo",
                "--connection-type",
                "eice",
                "--os-user",
                "ec2-user",
                "--ssh-port",
                "22",
            ],
        )

    @mock.patch("ec2connect.util.aws.shutil")
    @mock.patch("ec2connect.util.aws.os")
    def test_instance_connect_custom_params(self, mock_os, mock_shutil):
        mock_shutil.which.return_value = "aws"

        instance_connect(
            profile="default",
            region="region",
            instance={"instance_id": "i-foo"},
            os_user="ubuntu",
            ssh_port="2222",
            private_key_file="foo",
            debug=True,
        )

        mock_os.execvp.assert_called_once_with(
            "aws",
            [
                "aws",
                "--profile",
                "default",
                "--region",
                "region",
                "ec2-instance-connect",
                "ssh",
                "--instance-id",
                "i-foo",
                "--connection-type",
                "eice",
                "--os-user",
                "ubuntu",
                "--ssh-port",
                "2222",
                "--private-key-file",
                "foo",
                "--debug",
            ],
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_private_dns(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        mock_shutil.which.side_effect = ["ssh-keygen", "aws"]

        instance_connect_key(
            profile="default",
            region="region",
            instances={
                "instance_id": "i-foo",
                "public_dns": None,
                "private_dns": "foo.bar",
            },
            private_key_file=Path("/foo/bar"),
        )

        mock_os.remove.assert_has_calls(
            [mock.call(Path("/foo/bar")), mock.call(Path("/foo/bar.pub"))]
        )
        mock_run.assert_has_calls(
            [
                mock.call(
                    [
                        "ssh-keygen",
                        "-t",
                        "ed25519",
                        "-N",
                        "",
                        "-C",
                        "ec2connect@auto",
                        "-f",
                        Path("/foo/bar"),
                    ],
                    check=True,
                    capture_output=True,
                ),
                mock.call(
                    [
                        "aws",
                        "--profile",
                        "default",
                        "--region",
                        "region",
                        "ec2-instance-connect",
                        "send-ssh-public-key",
                        "--instance-id",
                        "i-foo",
                        "--instance-os-user",
                        "ec2-user",
                        "--ssh-public-key",
                        "file:///foo/bar.pub",
                    ],
                    check=True,
                    capture_output=True,
                ),
            ]
        )
        mock_echo.assert_called_once_with(
            "You have 60 seconds to log in to foo.bar with /foo/bar"
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_private_dns(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        mock_shutil.which.side_effect = ["ssh-keygen", "aws"]

        instance_connect_key(
            profile="default",
            region="region",
            instances={
                "instance_id": "i-foo",
                "public_dns": None,
                "private_dns": "foo.bar",
            },
            private_key_file=Path("/foo/bar"),
            debug=True,
        )

        mock_run.assert_has_calls(
            [
                mock.call(
                    [
                        "aws",
                        "--profile",
                        "default",
                        "--region",
                        "region",
                        "ec2-instance-connect",
                        "send-ssh-public-key",
                        "--instance-id",
                        "i-foo",
                        "--instance-os-user",
                        "ec2-user",
                        "--ssh-public-key",
                        "file:///foo/bar.pub",
                        "--debug",
                    ],
                    check=True,
                    capture_output=True,
                )
            ]
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_public_dns(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        instance_connect_key(
            profile="default",
            region="region",
            instances={
                "instance_id": "i-foo",
                "public_dns": "foo.baz",
                "private_dns": "foo.bar",
            },
            private_key_file=Path("/foo/bar"),
        )

        mock_echo.assert_called_once_with(
            "You have 60 seconds to log in to foo.baz with /foo/bar"
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_ssh_suggestions(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        instance_connect_key(
            profile="default",
            region="region",
            instances=[
                {
                    "instance_id": "i-foo",
                    "public_dns": "foo.baz",
                    "private_dns": "foo.bar",
                },
                {
                    "instance_id": "i-foo",
                    "public_dns": None,
                    "private_dns": "private.domain",
                },
            ],
            private_key_file=Path("/foo/bar"),
        )

        mock_echo.assert_has_calls(
            [
                mock.call("You have 60 seconds to log in to foo.baz with /foo/bar"),
                mock.call(
                    "You have 60 seconds to log in to private.domain with /foo/bar"
                ),
                mock.call(
                    "Example SSH command:\nssh -o ProxyCommand=\"ssh -i /foo/bar -W '[%h]:%p' ec2-user@foo.baz\" -i /foo/bar ec2-user@private.domain"
                ),
                mock.call(
                    "Example SCP command:\nscp -o ProxyCommand=\"ssh -i /foo/bar -W '[%h]:%p' ec2-user@foo.baz\" -i /foo/bar <file> ec2-user@private.domain:<file>"
                ),
            ]
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_no_fail_os_remove(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        mock_os.remove.side_effect = FileNotFoundError()

        instance_connect_key(
            profile="default",
            region="region",
            instances={
                "instance_id": "i-foo",
                "public_dns": "foo.baz",
                "private_dns": "foo.bar",
            },
            private_key_file=Path("/foo/bar"),
        )

        mock_echo.assert_called_once_with(
            "You have 60 seconds to log in to foo.baz with /foo/bar"
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_ssh_keygen_not_found(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        mock_shutil.which.return_value = None

        with pytest.raises(click.UsageError) as e:
            instance_connect_key(
                profile="default",
                region="region",
                instances={
                    "instance_id": "i-foo",
                    "public_dns": "foo.baz",
                    "private_dns": "foo.bar",
                },
                private_key_file=Path("/foo/bar"),
            )

        assert (
            e.value.message
            == "ssh-keygen could not be found on PATH, is openssh-client installed?"
        )

    @mock.patch("ec2connect.util.aws.echo")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.os")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_instance_connect_key_ssh_keypair_fails(
        self, mock_shutil, mock_os, mock_run, mock_echo
    ):
        mock_run.side_effect = CalledProcessError(
            1, cmd="ssh-keygen", output="some messsage"
        )

        with pytest.raises(click.UsageError) as e:
            instance_connect_key(
                profile="default",
                region="region",
                instances={
                    "instance_id": "i-foo",
                    "public_dns": "foo.baz",
                    "private_dns": "foo.bar",
                },
                private_key_file=Path("/foo/bar"),
            )

        assert e.value.message == "Error generating SSH key: some messsage"
