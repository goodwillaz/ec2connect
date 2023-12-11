"""State class"""

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

import click

from ec2connect.util.config import Config


class State:
    """State class"""
    def __init__(self, config: Config = None, debug: bool = False):
        self._config = config
        self._debug = debug

    @property
    def config(self) -> Config | None:
        """

        Returns: Config | None

        """
        return self._config or None

    @config.setter
    def config(self, value: Config) -> None:
        self._config = value

    @property
    def debug(self) -> bool:
        """

        Returns: bool

        """
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        self._debug = value


pass_state = click.make_pass_decorator(State)
