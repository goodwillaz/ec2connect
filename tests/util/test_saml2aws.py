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
import pytest
from subprocess import CompletedProcess
from unittest import mock, TestCase

import click
from click.testing import CliRunner
from questionary import Choice
from pyfakefs.fake_filesystem_unittest import patchfs

from ec2connect.util.config import Config
from ec2connect.util.saml2aws import iam_roles, present, load_saml2aws
from ec2connect.util.state import State

pass_config = click.make_pass_decorator(Config, ensure=True)


class Saml2awsTestCase(TestCase):
    @mock.patch("ec2connect.util.saml2aws.shutil")
    @mock.patch("ec2connect.util.saml2aws.run")
    def test_saml2aws_iam_roles_none(self, mock_run, mock_shutil):
        mock_shutil.which.return_value = "saml2aws"
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="")

        result = iam_roles(region="region")

        assert len(result) == 0
        mock_run.assert_called_with(
            [
                "saml2aws",
                "list-roles",
                "--skip-prompt",
                "--cache-saml",
                "--region",
                "region",
            ],
            capture_output=True,
            check=True,
            text=True,
        )

    @mock.patch("ec2connect.util.saml2aws.shutil")
    @mock.patch("ec2connect.util.saml2aws.run")
    def test_saml2aws_iam_roles_debug(self, mock_run, mock_shutil):
        mock_shutil.which.return_value = "saml2aws"
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="")

        result = iam_roles(region="region", debug=True)

        assert len(result) == 0
        mock_run.assert_called_with(
            [
                "saml2aws",
                "list-roles",
                "--skip-prompt",
                "--cache-saml",
                "--region",
                "region",
                "--verbose",
            ],
            capture_output=True,
            check=True,
            text=True,
        )

    @mock.patch("ec2connect.util.saml2aws.shutil")
    @mock.patch("ec2connect.util.saml2aws.run")
    def test_saml2aws_iam_roles_one(self, mock_run, mock_shutil):
        mock_shutil.which.return_value = "saml2aws"
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="""
Using IdP Account default to access Okta https://somedomain.okta.com/home/amazon_aws/123456789/272

Account: Account1 (123456789123)
arn:aws:iam::123456789123:role/Role1
""",
        )

        result = iam_roles(region="region")

        mock_run.assert_called_with(
            [
                "saml2aws",
                "list-roles",
                "--skip-prompt",
                "--cache-saml",
                "--region",
                "region",
            ],
            capture_output=True,
            check=True,
            text=True,
        )

        assert len(result) == 1
        assert isinstance(result[0], Choice)

        assert result[0].title == "arn:aws:iam::123456789123:role/Role1 (Account1)"
        assert result[0].value == "arn:aws:iam::123456789123:role/Role1"

    @mock.patch("ec2connect.util.saml2aws.shutil")
    @mock.patch("ec2connect.util.saml2aws.run")
    def test_saml2aws_iam_roles(self, mock_run, mock_shutil):
        mock_shutil.which.return_value = "saml2aws"
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="""
Using IdP Account default to access Okta https://somedomain.okta.com/home/amazon_aws/123456789/272

Account: Account1 (123456789123)
arn:aws:iam::123456789123:role/Role1

Account: Account2 (123456789012)
arn:aws:iam::123456789012:role/Role1
arn:aws:iam::123456789012:role/Role2
""",
        )

        result = iam_roles(region="region")

        mock_run.assert_called_with(
            [
                "saml2aws",
                "list-roles",
                "--skip-prompt",
                "--cache-saml",
                "--region",
                "region",
            ],
            capture_output=True,
            check=True,
            text=True,
        )

        assert len(result) == 3
        assert isinstance(result[0], Choice)
        assert isinstance(result[1], Choice)
        assert isinstance(result[2], Choice)

        assert result[0].title == "arn:aws:iam::123456789123:role/Role1 (Account1)"
        assert result[1].title == "arn:aws:iam::123456789012:role/Role1 (Account2)"
        assert result[2].title == "arn:aws:iam::123456789012:role/Role2 (Account2)"

        assert result[0].value == "arn:aws:iam::123456789123:role/Role1"
        assert result[1].value == "arn:aws:iam::123456789012:role/Role1"
        assert result[2].value == "arn:aws:iam::123456789012:role/Role2"

    @mock.patch("ec2connect.util.saml2aws.shutil")
    def test_has_saml2aws(self, mock_shutil):
        mock_shutil.which.side_effect = ["saml2aws", None]

        assert present() == True
        assert present() == False

    @patchfs
    @mock.patch("ec2connect.util.saml2aws.run")
    @mock.patch("ec2connect.util.saml2aws.shutil")
    def test_load_saml2aws(self, fs, mock_shutil, mock_run) -> None:
        mock_shutil.which.return_value = "saml2aws"

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = State(config=Config())
            ctx.obj.config.saml2aws_iam_role = "foo"

        @cli.command()
        @load_saml2aws
        def foo():
            pass

        runner = CliRunner()
        runner.invoke(cli, "foo", standalone_mode=False, catch_exceptions=False)

        mock_run.assert_called_with(
            [
                "saml2aws",
                "login",
                "--cache-saml",
                "--profile",
                "default",
                "--skip-prompt",
                "--role",
                "foo",
            ],
            check=True,
        )

    @patchfs
    @mock.patch("ec2connect.util.saml2aws.run")
    @mock.patch("ec2connect.util.saml2aws.shutil")
    def test_load_saml2aws_debug(self, fs, mock_shutil, mock_run) -> None:
        mock_shutil.which.return_value = "saml2aws"

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = State(config=Config())
            ctx.obj.debug = True
            ctx.obj.config.saml2aws_iam_role = "foo"

        @cli.command()
        @load_saml2aws
        def foo():
            pass

        runner = CliRunner()
        runner.invoke(cli, "foo", standalone_mode=False, catch_exceptions=False)

        mock_run.assert_called_with(
            [
                "saml2aws",
                "login",
                "--cache-saml",
                "--profile",
                "default",
                "--skip-prompt",
                "--role",
                "foo",
                "--verbose",
            ],
            check=True,
        )

    @patchfs
    @mock.patch("ec2connect.util.saml2aws.run")
    @mock.patch("ec2connect.util.saml2aws.shutil")
    def test_load_saml2aws_no_profile(self, fs, mock_shutil, mock_run) -> None:
        mock_shutil.which.return_value = "saml2aws"

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = State(config=Config())

        @cli.command()
        @load_saml2aws
        def foo():
            pass

        runner = CliRunner()
        with pytest.raises(click.UsageError) as e:
            runner.invoke(cli, "foo", standalone_mode=False, catch_exceptions=False)

        assert (
            e.value.message
            == "saml2aws is installed but no profile is set.  Please run 'ec2connect configure'"
        )

    @mock.patch("ec2connect.util.saml2aws.run")
    @mock.patch("ec2connect.util.saml2aws.shutil")
    def test_load_saml2aws_no_saml2aws(self, mock_shutil, mock_run) -> None:
        mock_shutil.which.return_value = None

        @click.group()
        @click.pass_context
        def cli(ctx):
            ctx.obj = State()

        @cli.command()
        @load_saml2aws
        def foo():
            pass

        runner = CliRunner()
        runner.invoke(cli, "foo", standalone_mode=False, catch_exceptions=False)

        mock_run.assert_not_called()
