import requests
import os
import json
import click
import logging

from nngrid.constants import *

@click.group()
def controll():
    pass


@click.command("restart")
def restart():
    config_path =  os.path.join(STATE["project_path"], "config.json")
    config = json.load(config_path)
    requests.get(f'http://localhost:{STATE["port"]}/restart')
    logging.info("Restarted")

controll.add_command()