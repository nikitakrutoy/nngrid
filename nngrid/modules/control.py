import requests
import os
import json
import click
import logging

from nngrid.constants import *

@click.command("control")
@click.argument("command")
def run(command):
    requests.get(f'http://localhost:{STATE["port"]}/{command}')
    logging.info(f"{command}ed")