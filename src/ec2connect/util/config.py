"""Config class"""

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
from configparser import ConfigParser
from functools import update_wrapper
from pathlib import Path

from xdg import xdg_config_home

logger = logging.getLogger("ec2connect.config")


def _profile_exists(f):
    def exists(*args):
        logger.debug("Ensuring %s profile exists", args[0].profile)
        if not args[0].has_section(args[0].profile):
            args[0][args[0].profile] = {}

        f(*args)

    return update_wrapper(exists, f)


class Config(ConfigParser):
    """
    A Config class
    """

    def __init__(self, profile: str = "default", **kwargs):
        super().__init__(**kwargs)

        logger.debug("Using %s profile for configuration", profile)
        self._profile = profile

        self._config_file = None

    @staticmethod
    def default_config_file() -> Path:
        """

        Returns: Path to config file

        """
        return Path(xdg_config_home()) / "ec2connect" / "config"

    @property
    def config_file(self) -> Path | None:
        """

        Returns: Config file path

        """
        return self._config_file

    @property
    def profile(self) -> str:
        """

        Returns: Returns profile set for Config

        """
        return self._profile

    @property
    def key(self) -> Path:
        """

        Returns: Path to key

        """
        key = self.get(self._profile, "key", fallback=None)
        return Path(key).expanduser().resolve() if key is not None else key

    @key.setter
    @_profile_exists
    def key(self, key: Path | str) -> None:
        self.set(
            self._profile, "key", str(key.expanduser().resolve()) if isinstance(key, Path) else key
        )

    @property
    def saml2aws_iam_role(self) -> str | None:
        """

        Returns: saml2aws iam role to use for this profile

        """
        return self.get(self._profile, "saml2aws_iam_role", fallback=None)

    @saml2aws_iam_role.setter
    @_profile_exists
    def saml2aws_iam_role(self, role: str) -> None:
        self.set(self._profile, "saml2aws_iam_role", role)

    @property
    def aws_region(self) -> str | None:
        """

        Returns: default aws region to use

        """
        return self.get(self._profile, "aws_region", fallback=None)

    @aws_region.setter
    @_profile_exists
    def aws_region(self, aws_region: str) -> None:
        self.set(self._profile, "aws_region", aws_region)

    def read(self, filenames: Path | str = None, encoding: str | None = None):
        """

        Args:
            encoding:
            filenames:
        """
        self._config_file = Path(
            self.default_config_file() if not filenames else filenames
        )

        logger.debug("Loading configuration from %s", self._config_file)

        super().read(filenames=self._config_file, encoding=encoding)

    def write(self, fp=None, space_around_delimiters=True) -> None:
        """

        Method to write the config to file

        """
        config_file = self.config_file
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with config_file.open("w", encoding="utf-8") as file:
            logger.debug("Writing to config file: %s", config_file)
            super().write(file, space_around_delimiters=space_around_delimiters)
