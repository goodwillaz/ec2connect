<!-- These are examples of badges you might want to add to your README:
     please update the URLs accordingly

[![Built Status](https://api.cirrus-ci.com/github/<USER>/ec2connect.svg?branch=main)](https://cirrus-ci.com/github/<USER>/ec2connect)
[![ReadTheDocs](https://readthedocs.org/projects/ec2connect/badge/?version=latest)](https://ec2connect.readthedocs.io/en/stable/)
[![Coveralls](https://img.shields.io/coveralls/github/<USER>/ec2connect/main.svg)](https://coveralls.io/r/<USER>/ec2connect)
[![PyPI-Server](https://img.shields.io/pypi/v/ec2connect.svg)](https://pypi.org/project/ec2connect/)
[![Conda-Forge](https://img.shields.io/conda/vn/conda-forge/ec2connect.svg)](https://anaconda.org/conda-forge/ec2connect)
[![Monthly Downloads](https://pepy.tech/badge/ec2connect/month)](https://pepy.tech/project/ec2connect)
[![Twitter](https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter)](https://twitter.com/ec2connect)
-->

# ec2connect

> Utility to connect to ec2 instances through EC2 Instance Connect

# Prereqs

* Python 3.10+
* AWS CLI 2+
* An [EC2 Instance Connect Endpoint](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-using-eice.html) setup and configured
* EC2 instances that support Instance Connect
* saml2aws (optional)

# Installation

The easiest method is directly with pip, however virtual environments and pipenv are recommended

> $ pip install ec2connect

or

> $ pipenv install ec2connect 

# Configuration

If you are using saml2aws to log into AWS via a federated identity, ensure that it is configured first with credentials saved.  You should be able to run `saml2aws list-roles --skip-prompt` and get a list of roles that saml2aws has access to without user interaction.

Next you can configure ec2connect.  Just like saml2aws and the aws cli, it supports multiple profiles and will properly use those in those tools.  You can pass the `--profile <profile>` option and this is the profile that will be used to store saml2aws credentials (optional) and that will be used for the AWS CLI calls (you can configure ~/.aws/credentials as needed as well)

These commands should be run in whichever Python environment you installed them.  If using virtualenv, activate your environment.  If using pipenv, use either `pipenv shell` or prefix the commands with `pipenv run`.

> ec2connect configure

> ec2connect --profile myprofile configure

# Usage

For expanded help, use the `--help` flag on any command.

To SSH into an instance, use the following
> ec2connect ssh

To drop a public key into Instance Connect for an instance to use (good for normal SSH connections or SCP file transfers)
> ec2connect key
