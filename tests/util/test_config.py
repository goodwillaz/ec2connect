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
import os

from pathlib import Path
from unittest import mock, TestCase

from pyfakefs.fake_filesystem_unittest import patchfs

from ec2connect.util.config import Config


class ConfigTestCase(TestCase):
    def test_config_init(self):
        config = Config()

        assert config.profile == "default"
        assert config.config_file is None

    def test_config_init_custom_parameters(self):
        config = Config(profile="custom")

        assert config.profile == "custom"

    @patchfs
    def test_reading_properties(self, fs):
        with open("/config.ini", mode="w", encoding="utf-8") as file:
            file.write(
                "[default]\nkey = /foo/bar\nsaml2aws_iam_role = some_role\naws_region = us-west-2"
            )

        config = Config()
        config.read("/config.ini")

        assert config.key == Path("/foo/bar")
        assert config.saml2aws_iam_role == "some_role"
        assert config.aws_region == "us-west-2"

    @patchfs
    @mock.patch("ec2connect.util.config.xdg_config_home")
    def test_reading_properties_default_config(self, fs, mock_xdg):
        mock_xdg.return_value = "/config"

        os.makedirs(os.path.dirname(Config.default_config_file()))
        with open(Config.default_config_file(), mode="w", encoding="utf-8") as file:
            file.write(
                "[default]\nkey = /foo/bar\nsaml2aws_iam_role = some_role\naws_region = us-west-2"
            )

        config = Config()
        config.read()

        assert config.config_file == Path("/config/ec2connect/config")
        assert config.key == Path("/foo/bar")
        assert config.saml2aws_iam_role == "some_role"
        assert config.aws_region == "us-west-2"

    @patchfs
    def test_write_properties(self, fs):
        config = Config()
        config.read("/config.ini")

        config.key = "/foo/bar"
        config.saml2aws_iam_role = "foo_role"
        config.aws_region = "us-west-1"
        config.write()

        assert config.key == Path("/foo/bar")
        assert config.saml2aws_iam_role == "foo_role"
        assert config.aws_region == "us-west-1"

        with open("/config.ini") as file:
            assert (
                file.read()
                == "[default]\nkey = /foo/bar\nsaml2aws_iam_role = foo_role\naws_region = us-west-1\n\n"
            )
