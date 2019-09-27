import requests
import os
import json
import click
import logging

from nngrid.constants import *

@click.command("control")
@click.argument("c")
def run(c):
    if c == "restart":
        restart()

def restart():
    with open(os.path.join(STATE["project_path"], "config.json")) as f:
        config = json.load(f)
    requests.get(f'http://localhost:{STATE["port"]}/restart')
    logging.info("Restarted")
