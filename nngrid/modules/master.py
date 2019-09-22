from flask import Flask, request, send_file, Response, jsonify
from filelock import Timeout, FileLock
import io
import torch
import pickle
import json
import click
import subprocess
import nngrid.tasks
import sys
import importlib as im
from hashlib import md5

from nngrid.constants import *
from nngrid.utils import ExpandedPath


class Master(Flask):
    @staticmethod
    def _run_gunicron():
        host = "127.0.0.1" if STATE["local"] else "0.0.0.0"
        port = STATE["port"]
        address = f"{host}:{port}"
        current_dir = os.path.dirname(__file__)
        command = [
            "gunicorn", "nngrid.modules.master:APP", "-b", address, "--chdir", current_dir
        ]
        subprocess.call(command)

    def _run_dev(self):
        host = "127.0.0.1" if STATE["local"] else "0.0.0.0"
        port = STATE["port"]
        super().run(host=host, port=port, debug=True)

    def run(
            self,
            project,
            port=8088,
            mode="sync",
            local=True,
            dev=True,
            config=None,
            workers_num=-1,
    ):
        *_, project_name = os.path.abspath(project).split("/")
        STATE.mset(dict(
            project_name=project_name,
            project_path=os.path.expanduser(project),
        ))

        # loading worker config
        config_path = os.path.join(project, 'config.json') if config is None else config
        with open(config_path, "r") as f:
            STATE.mset(json.load(f))

        STATE.mset(dict(
            port=port,
            mode=mode,
            workers_num=workers_num,
            project=project,
            local=local
        ))

        if dev:
            STATE["status"] = "serving"
            self._run_dev()
        else:
            STATE["status"] = "started"
            self._run_gunicron()


APP = Master(__name__)


@APP.route("/")
def hello():
    return "This master server"


@APP.route("/ping")
def ping():
    return "pong"

@APP.route("/getid")
def getid():
    return md5(str(request.headers).encode()).hexdigest()


@APP.route("/update", methods=["POST"])
def update():
    updates = os.listdir(UPDATES_DIR)
    if STATE["mode"] == "sync" and len(updates) + 1 >= STATE["workers_num"]:
        STATE["status"] = "aggregating"
    data = request.get_data()
    nngrid.tasks.update(data)
    return Response(status=200)


@APP.route("/pull", methods=["GET"])
def pull():
    if STATE["status"] == "serving":
        model_state_path = os.path.join(STATE["project_path"], "states", "model_state.torch")
        model_state_path_lock = model_state_path + ".lock"
        if os.path.isfile(model_state_path):
            with FileLock(model_state_path_lock, timeout=1) as lock:
                model_state = torch.load(model_state_path)
        else:
            sys.path.append(os.path.expanduser(STATE["project_path"]))
            model_state = im.import_module('model').Model(**STATE["model_config"]).state_dict()
            if not os.path.exists(os.path.join(STATE["project_path"], "states", )):
                os.mkdir(os.path.join(STATE["project_path"], "states"))
                torch.save(model_state, model_state_path)

        return send_file(
            io.BytesIO(pickle.dumps(model_state)),
            attachment_filename="data",
        )
    else:
        return Response("Busy now. Go play with your toys, son.", status=503)


@APP.route("/start")
def start():
    STATE["status"] = "distributing"
    return Response(status=200)


@click.command("master")
@click.argument("project", required=1, type=ExpandedPath(exists=True, resolve_path=True))
@click.option("--port", "-p", type=int, default=8088)
@click.option("--mode", "-m", type=click.Choice(['sync', 'async'],), default='async')
@click.option("--local", "-l", is_flag=True)
@click.option("--dev", is_flag=True)
@click.option("--config", "-c", type=str)
@click.option("--workers_num", "-w", default=-1)
def run(*args, **kwargs):
    APP.run(*args, **kwargs)
