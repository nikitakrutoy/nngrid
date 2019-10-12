from flask import Flask, request, send_file, Response, jsonify
from filelock import Timeout, FileLock
import io
import torch
import pickle
import json
import click
import subprocess
import binascii
import nngrid.tasks as tasks
import sys
import logging
import importlib as im
from hashlib import md5
from uuid import uuid1

from nngrid.constants import *
from nngrid.utils import ExpandedPath, nukedir, PostgressMetricsConnector

import time

logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger("pickle").setLevel(logging.INFO)

class Master(Flask):
    @staticmethod
    def _run_gunicron():
        host = "127.0.0.1" if STATE["local"] else "0.0.0.0"
        port = STATE["port"]
        address = f"{host}:{port}"
        current_dir = os.path.dirname(__file__)
        command = [
            "gunicorn", "nngrid.modules.master:APP", "-b", address, "--chdir", current_dir,
            "--access-logfile", '-',
            "--error-logfile", '-',
            '--timeout', '1000',
            '-w', str(STATE['workers_num']),
            '-c', 'python:nngrid.gunicorn_config'
        ]
        logging.debug(" ".join(command))
        subprocess.call(command)

    def _run_dev(self):
        host = "127.0.0.1" if STATE["local"] else "0.0.0.0"
        port = STATE["port"]
        super().run(host=host, port=port, debug=True, threaded=True)

    def run(
            self,
            project,
            port=8088,
            mode="sync",
            local=True,
            dev=True,
            config=None,
            workers_num=-1,
            run_name=None,
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
            local=local,
            run_id=uuid1().hex if run_name is None else run_name
        ))

        if dev:
            STATE["status"] = "serving"
            self._run_dev()
        else:
            STATE["status"] = "idle"
            self._run_gunicron()


APP = Master(__name__)


@APP.route("/")
def hello():
    return "This master server"


@APP.route("/ping")
def ping():
    return "pong"

@APP.route("/init")
def init_worker():
    db = PostgressMetricsConnector("localhost")
    remote_addr = str(request.environ['REMOTE_ADDR'])
    pid = str(request.args.get("pid"))
    worker_id = md5((remote_addr + pid).encode()).hexdigest()

    query = "SELECT MAX(step) as last_step, SUM(compute_time) as compute_time " \
        "FROM data " \
        f"WHERE run_id = '{STATE['run_id']}' "\
        f"AND worker_id = '{worker_id}' "
    last_step, compute_time = db.fetchone(query)
    db.conn.close()
    return jsonify(worker_id, last_step, compute_time)

@APP.route("/metrics", methods=["POST"])
def metrics():
    if STATE["status"] == "serving":
        tasks.metrics(binascii.b2a_base64(request.get_data()).decode())
    return Response(status=200)

@APP.route("/update", methods=["POST"])
def update():
    if STATE["status"] == "serving":
        updates = os.listdir(UPDATES_DIR)
        if STATE["mode"] == "sync" and len(updates) + 1 >= STATE["workers_num"]:
            STATE["status"] = "aggregating"
        tasks.update(request.get_data())
    return Response(status=200)


@APP.route("/lr_change", methods=["GET"])
def lr_change():
    tasks.lr_change(float(request.args.get("lr")))
    return Response(status=200)



@APP.route("/pull", methods=["GET"])
def pull():
    start_lock = time.time()
    if STATE["status"] == "serving":
        states_dir = os.path.join(STATE["project_path"], "states",)
        model_state_path = os.path.join(states_dir, "model_state.torch")
        lock_path = os.path.join(states_dir, "lock")
        lock = FileLock(lock_path, timeout=-1)
        try:
            with lock.acquire(poll_intervall=POLL_INTERVAL):
                start_read = time.time()
                if os.path.isfile(model_state_path):
                    model_state = torch.load(model_state_path)
                else:
                    sys.path.append(os.path.expanduser(STATE["project_path"]))
                    model_state = im.import_module('model').Model(**STATE["model_config"]).state_dict()
                    if not os.path.exists(os.path.join(STATE["project_path"], "states", )):
                        os.mkdir(os.path.join(STATE["project_path"], "states"))
                        torch.save(model_state, model_state_path)
                logging.debug("Read time " + str(time.time() - start_read))
            
            logging.debug("Lock time " + str(time.time() - start_lock))
            return send_file(
                io.BytesIO(pickle.dumps(model_state)),
                attachment_filename="data",
            )
        except TimeoutError as e:
            return Response("Busy now. Go play with your toys, son.", status=503)
    else:
        return Response("Busy now. Go play with your toys, son.", status=503)


@APP.route("/start")
def start():
    STATE["status"] = "serving"
    return Response(status=200)

@APP.route("/stop")
def stop():
    STATE["status"] = "idle"
    return Response(status=200)


@APP.route("/restart")
def restart():
    states_dir = os.path.join(STATE["project_path"], "states",)
    model_state_path = os.path.join(states_dir, "model_state.torch")
    opt_state_path = os.path.join(states_dir, "opt_state.torch")
    lock_path = os.path.join(states_dir, "lock")

    # removing update
    list(map(
        lambda path: os.remove(path),
        map(
            lambda file: os.path.join(UPDATES_DIR, file), 
            os.listdir(UPDATES_DIR)
        )
    ))
    lock = FileLock(lock_path, timeout=-1)
    with  lock.acquire(poll_intervall=POLL_INTERVAL):
        os.remove(model_state_path)
        os.remove(opt_state_path)
    
    STATE.set("run_id", uuid1().hex)
    return Response(status=200)



@click.command("master")
@click.argument("project", required=1, type=ExpandedPath(exists=True, resolve_path=True))
@click.option("--port", "-p", type=int, default=5000)
@click.option("--mode", "-m", type=click.Choice(['sync', 'async', 'hogwild'],), default='async')
@click.option("--local", "-l", is_flag=True)
@click.option("--dev", is_flag=True)
@click.option("--config", "-c", type=str)
@click.option("--workers_num", "-w", default=3)
@click.option("--run_name", type=str)
def run(*args, **kwargs):
    APP.run(*args, **kwargs)
