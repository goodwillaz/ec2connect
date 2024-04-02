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

from pathlib import Path
from unittest import mock
from unittest.mock import call

import click
from click.testing import CliRunner
from pyfakefs.fake_filesystem_unittest import TestCase

from ec2connect import console
from ec2connect.util import state
from ec2connect.util.config import Config


class ConsoleTestCase(TestCase):

    def setUp(self):
        patch_saml2aws_present = mock.patch('ec2connect.console.saml2aws.present')
        self.addCleanup(patch_saml2aws_present.stop)
        self.mock_saml2aws_present = patch_saml2aws_present.start()
        self.mock_saml2aws_present.return_value = False

    @mock.patch("ec2connect.console.logging")
    def test_base_group(self, mock_logging):
        with mock.patch("ec2connect.console.logging.INFO", 20):

            @console.cli.command()
            @click.pass_context
            def foo(ctx):
                assert isinstance(ctx.obj, state.State)
                assert ctx.obj.debug is False

            CliRunner().invoke(console.cli, "foo", catch_exceptions=False)
            assert (
                mock_logging.mock_calls
                == call.getLogger("ec2connect").setLevel(mock_logging.INFO).call_list()
            )

    @mock.patch("ec2connect.console.botocore")
    @mock.patch("ec2connect.console.logging")
    def test_base_group_debug(self, mock_logging, mock_botocore):
        with mock.patch("ec2connect.console.logging.INFO", 20):
            with mock.patch("ec2connect.console.logging.DEBUG", 30):

                @console.cli.command()
                def foo():
                    pass

                CliRunner().invoke(console.cli, "--debug foo", catch_exceptions=False)
                assert mock_logging.mock_calls == [
                    *call.getLogger("ec2connect")
                    .setLevel(mock_logging.INFO)
                    .call_list(),
                    *call.getLogger("ec2connect")
                    .setLevel(mock_logging.DEBUG)
                    .call_list(),
                ]
                assert (
                    mock_botocore.mock_calls
                    == call.session.get_session().set_debug_logger().call_list()
                )

    @mock.patch.object(Config, "write")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.console.saml2aws")
    def test_configure_zero_config(
        self, mock_saml2aws, mock_questionary, mock_config_write
    ):
        mock_saml2aws.present.return_value = True
        mock_saml2aws.iam_roles.return_value = []
        mock_questionary.select.return_value.ask.return_value = "foobar"
        mock_questionary.text.return_value.ask.side_effect = ["aws-region", "/foo/key"]

        local_state = state.State(config=Config())
        CliRunner().invoke(
            console.cli, "configure", catch_exceptions=False, obj=local_state
        )

        mock_saml2aws.iam_roles.assert_called_with("default", False)
        assert mock_questionary.mock_calls == [
            *call.select(
                message="IAM Role", default=None, choices=[], use_shortcuts=True
            )
            .ask()
            .call_list(),
            *call.text(message="Default AWS Region", default="").ask().call_list(),
            *call.text(message="Private SSH Key Path", default="").ask().call_list(),
        ]

        assert local_state.config.aws_region == "aws-region"
        assert local_state.config.saml2aws_iam_role == "foobar"
        assert local_state.config.key == Path("/foo/key")

        mock_config_write.assert_called()

    @mock.patch.object(Config, "write")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.console.saml2aws")
    def test_configure_no_saml2aws(
        self, mock_saml2aws, mock_questionary, mock_config_write
    ):
        mock_saml2aws.present.return_value = False
        mock_questionary.text.return_value.ask.side_effect = ["aws-region", "/foo/key"]

        local_state = state.State(config=Config())
        CliRunner().invoke(
            console.cli, "configure", catch_exceptions=False, obj=local_state
        )

        mock_saml2aws.iam_roles.assert_not_called()
        assert local_state.config.saml2aws_iam_role is None

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_ssh(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.select.return_value.ask.return_value = {"instance_id": "i-foobar"}

        local_state = state.State(config=Config())
        CliRunner().invoke(console.cli, "ssh", standalone_mode=False, catch_exceptions=False, obj=local_state)

        mock_aws.instance_connect.assert_called_with(profile='default', region=None, instance={"instance_id": "i-foobar"}, debug=False, os_user='ec2-user', ssh_port='22', private_key_file=None)
        mock_aws.instance_choices.assert_called_with(profile='default', region=None)

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_ssh_no_selection(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.select.return_value.ask.return_value = None

        local_state = state.State(config=Config())
        result = CliRunner().invoke(console.cli, "ssh", catch_exceptions=False, obj=local_state)

        assert result.exit_code == 1
        mock_aws.instance_connect.assert_not_called()
        mock_aws.instance_choices.assert_called_with(profile='default', region=None)

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_ssh_custom_arguments(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.select.return_value.ask.return_value = {"instance_id": "i-foobar"}

        local_state = state.State(config=Config())
        CliRunner().invoke(console.cli, "ssh -u user -p 2222 -k /foo/bar", catch_exceptions=False, obj=local_state)

        mock_aws.instance_connect.assert_called_with(profile='default', region=None, instance={"instance_id": "i-foobar"}, debug=False, os_user='user', ssh_port='2222', private_key_file='/foo/bar')

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_key_config(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.checkbox.return_value.ask.return_value = {"instance_id": "i-foobar"}

        local_state = state.State(config=Config())
        local_state.config.key = Path('/foo/bar.key')
        CliRunner().invoke(console.cli, "key", catch_exceptions=False, obj=local_state)

        mock_aws.instance_connect_key.assert_called_with(profile='default', region=None, instances={'instance_id': 'i-foobar'}, debug=False, os_user='ec2-user', private_key_file='/foo/bar.key')

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_key_option(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.checkbox.return_value.ask.return_value = {"instance_id": "i-foobar"}

        local_state = state.State(config=Config())
        CliRunner().invoke(console.cli, "key -k /foo/bar.key", catch_exceptions=False, obj=local_state)

        mock_aws.instance_connect_key.assert_called_with(profile='default', region=None, instances={'instance_id': 'i-foobar'}, debug=False, os_user='ec2-user', private_key_file='/foo/bar.key')

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_key_no_selection(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.checkbox.return_value.ask.return_value = None

        local_state = state.State(config=Config())
        local_state.config.key = Path('/foo/bar.key')
        result = CliRunner().invoke(console.cli, "key", catch_exceptions=False, obj=local_state)

        assert result.exit_code == 1
        mock_aws.instance_connect_key.assert_not_called()

    @mock.patch("ec2connect.console.aws")
    @mock.patch("ec2connect.console.questionary")
    @mock.patch("ec2connect.util.aws.run")
    @mock.patch("ec2connect.util.aws.shutil")
    def test_key_no_key(self, mock_shutil, mock_run, mock_questionary, mock_aws):
        mock_shutil.return_value = True
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="aws-cli/2.12 Python/3.11"
        )
        mock_questionary.checkbox.return_value.ask.return_value = None

        local_state = state.State(config=Config())

        with pytest.raises(click.UsageError) as e:
            CliRunner().invoke(console.cli, "key", standalone_mode=False, catch_exceptions=False, obj=local_state)

        assert e.value.message == "No key is specified, please run 'ec2connect configure' or specify the --private-key-file option"
        mock_aws.instance_connect_key.assert_not_called()
