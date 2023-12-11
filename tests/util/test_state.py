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
from unittest import mock, TestCase

from pyfakefs.fake_filesystem_unittest import patchfs

from ec2connect.util.config import Config
from ec2connect.util.state import State


class StateTestCase(TestCase):
    def test_state_init(self):
        state = State()

        assert state.config is None
        assert state.debug is False

    def test_state_debug(self):
        state = State(debug=True)
        assert state.debug is True

        state.debug = False
        assert state.debug is False

    @mock.patch("ec2connect.util.config.xdg_config_home")
    def test_state_config(self, mock_xdg_config_home):
        mock_xdg_config_home.return_value = "/foo"
        state = State(config=Config())
        new_config = Config()

        assert isinstance(state.config, Config)

    @mock.patch("ec2connect.util.config.xdg_config_home")
    def test_state_config_set(self, mock_xdg_config_home):
        mock_xdg_config_home.return_value = "/foo"
        state = State()
        state.config = Config()

        assert isinstance(state.config, Config)
