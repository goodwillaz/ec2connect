"""Console application"""

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
import sys
from pathlib import Path

import botocore.session
import click
import questionary

from ec2connect.util import aws, config, saml2aws, state, validators

logging.basicConfig()
logger = logging.getLogger("ec2connect.console")


@click.group(context_settings={"auto_envvar_prefix": "EC2CONNECT"})
@click.pass_context
@click.option(
    "-p", "--profile", default="default", help="Profile to use", show_default=True
)
@click.option(
    "-c",
    "--config-file",
    help="Alternate config file",
    type=click.Path(exists=True),
    callback=lambda _, __, value: Path(value).expanduser().resolve() if value else None,
)
@click.option("-d", "--debug", is_flag=True)
@click.version_option()
def cli(ctx, profile: str, debug: bool, config_file: str = None):
    """Connect to EC2 instances with ease"""

    logging.getLogger("ec2connect").setLevel(logging.INFO)
    if debug:
        logging.getLogger("ec2connect").setLevel(logging.DEBUG)
        botocore.session.get_session().set_debug_logger()

    if ctx.obj is None:
        conf = config.Config(profile=profile)
        conf.read(filenames=config_file)
        ctx.obj = state.State(config=conf, debug=debug)


@cli.command()
@state.pass_state
def configure(local_state: state.State):
    """Configure ec2connect with basic options"""
    if saml2aws.present():
        local_state.config.saml2aws_iam_role = questionary.select(
            message="IAM Role",
            default=local_state.config.saml2aws_iam_role,
            choices=saml2aws.iam_roles(local_state.config.profile, local_state.debug),
            use_shortcuts=True,
        ).ask()

    local_state.config.aws_region = questionary.text(
        message="Default AWS Region", default=local_state.config.aws_region or ""
    ).ask()

    local_state.config.key = questionary.text(
        message="Private SSH Key Path",
        default=str(local_state.config.key)
        if local_state.config.key is not None
        else "",
    ).ask()

    local_state.config.write()


@cli.command()
@click.option("-u", "--os-user", help="Instance SSH User", default="ec2-user")
@click.option("-p", "--ssh-port", help="Instance SSH Port", default="22")
@click.option(
    "-k",
    "--private-key-file",
    help="Private SSH Keyfile to use",
    type=click.Path(resolve_path=True),
)
@saml2aws.load_saml2aws
@aws.validate_aws_cli
@state.pass_state
def ssh(local_state: state.State, **kwargs):
    """Connect to an instance via SSH"""
    instance = questionary.select(
        message="Choose an instance",
        choices=aws.instance_choices(
            profile=local_state.config.profile, region=local_state.config.aws_region
        ),
    ).ask()

    if instance is None:
        sys.exit(1)

    aws.instance_connect(
        profile=local_state.config.profile,
        region=local_state.config.aws_region,
        instance=instance,
        debug=local_state.debug,
        **kwargs
    )


@cli.command()
@click.option("-u", "--os-user", help="Instance SSH User", default="ec2-user")
@click.option(
    "-k",
    "--private-key-file",
    help="Private SSH Key",
    type=click.Path(),
    callback=lambda _, __, value: Path(value).expanduser().resolve() if value else None,
)
@saml2aws.load_saml2aws
@aws.validate_aws_cli
@state.pass_state
def key(local_state: state.State, **kwargs):
    """Push an SSH key to one or more servers for manual ssh or scp connections"""
    if local_state.config.key is None and not kwargs["private_key_file"]:
        raise click.UsageError(
            "No key is specified, please run 'ec2connect configure' or specify the --private-key-file option"
        )

    instances = questionary.checkbox(
        message="Choose instances",
        choices=aws.instance_choices(
            profile=local_state.config.profile, region=local_state.config.aws_region
        ),
        validate=validators.instance_validator,
    ).ask()

    if instances is None:
        sys.exit(1)

    kwargs["private_key_file"] = str(kwargs["private_key_file"] or local_state.config.key)

    aws.instance_connect_key(
        profile=local_state.config.profile,
        region=local_state.config.aws_region,
        instances=instances,
        debug=local_state.debug,
        **kwargs
    )


@cli.command()
@click.option("-i", "--instance", help="Instance to tunnel through")
@click.option("-l", "--local-port", help="Local port")
@click.option("-r", "--remote-port", help="Remote port", required=True)
@click.option("-e", "--endpoint", help="Endpoint to tunnel to", required=True)
@click.option("-u", "--os-user", help="Instance SSH User", default="ec2-user")
@click.option(
    "-k",
    "--private-key-file",
    help="Private SSH Keyfile to use",
    type=click.Path(resolve_path=True),
)
@saml2aws.load_saml2aws
@aws.validate_aws_cli
@state.pass_state
def tunnel(local_state: state.State, **kwargs):
    """Open a tunnel to some remote endpoint via an instance, via SSH"""
    if kwargs["instance"] is None:
        kwargs["instance"] = questionary.select(
            message="Choose an instance",
            choices=aws.instance_choices(
                profile=local_state.config.profile, region=local_state.config.aws_region
            ),
        ).ask()

    else:
        kwargs["instance"] = aws.get_instance(profile=local_state.config.profile, region=local_state.config.aws_region,
                                              instance_id=kwargs["instance"])

    if kwargs["instance"] is None:
        sys.exit(1)

    kwargs["private_key_file"] = str(kwargs["private_key_file"] or local_state.config.key)

    aws.tunnel(
        profile=local_state.config.profile,
        region=local_state.config.aws_region,
        debug=local_state.debug,
        **kwargs
    )
