"""saml2aws utility class"""

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

import re
import shutil
from functools import update_wrapper
from subprocess import run
from typing import Callable

import click
from click import UsageError
from questionary import Choice

from ec2connect.util import state


def load_saml2aws(f) -> Callable:
    """

    Args:
        f: wrapped function

    Returns: decorated function

    """

    @click.pass_context
    @state.pass_state
    def wrapper(local_state: state.State, ctx, *args, **kwargs):
        if present():
            if local_state.config.saml2aws_iam_role is None:
                raise UsageError(
                    "saml2aws is installed but no profile is set.  Please run 'ec2connect configure'"
                )

            saml2aws_args = [
                _find_saml2aws(),
                "login",
                "--cache-saml",
                "--profile",
                local_state.config.profile,
                "--skip-prompt",
                "--role",
                local_state.config.saml2aws_iam_role,
            ]

            if local_state.debug:
                saml2aws_args.append("--verbose")

            run(
                saml2aws_args,
                check=True,
            )
        return ctx.invoke(f, *args, **kwargs)

    return update_wrapper(wrapper, f)


def iam_roles(region: str, debug: bool = False) -> list[Choice]:
    """

    Returns: questionary Choice list of saml2aws roles

    """
    args = [
        _find_saml2aws(),
        "list-roles",
        "--skip-prompt",
        "--cache-saml",
        "--region",
        region,
    ]

    if debug:
        args.append("--verbose")

    output = run(
        args,
        capture_output=True,
        check=True,
        text=True,
    )
    choices = _parse_roles(output.stdout)
    return choices


def _parse_roles(response: str) -> list[Choice]:
    lines = response.splitlines()

    choices = []
    account = None
    for line in lines:
        match = re.match(r"^Account: (.*?) \(", line)
        account = match[1] if match is not None else account

        if re.match(r"^arn:aws:iam", line):
            choices.append(
                Choice(
                    title=f"{line} ({account})",
                    value=line,
                )
            )

    return choices


def present() -> bool:
    """

    Returns: bool

    """
    return _find_saml2aws() is not None


def _find_saml2aws() -> str | None:
    return shutil.which("saml2aws")
