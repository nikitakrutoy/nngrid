import requests
import os
import json
import click
import logging

from nngrid.constants import *

@click.command("control")
@click.argument("command")
@click.argument("lr", required=False)
def run(command, lr=None):
    requests.get(f'http://localhost:{STATE["port"]}/{command}', params=dict(lr=lr))
    logging.info(f"{command}ed")