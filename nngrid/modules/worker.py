from nngrid.constants import *
import importlib as im
import click
import pickle
import requests
import json
import nngrid.utils as utils
import visdom
import time
import logging
import sys
import subprocess
import numpy as np
import torch
from tqdm.auto import tqdm
from functools import reduce

device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

def step(model_state):
    logging.info("Doing model step")
    start_time = time.time()

    module = im.import_module('model')
    model = module.Model()
    model.load_state_dict(model_state)
    model = model.to(device)

    dataset = module.DatasetClass(
        root_path=os.path.join(state["project_path"]),
    )

    batch_size = state["batch_size"]
    if not state['eval']:
        start = np.random.randint(0, int(len(dataset) * 0.8 - batch_size)) 
        X, y = dataset[start: start + batch_size]
    else:
        start = int(len(dataset) * 0.8 - batch_size)
        X, y = dataset[start:start + 20]
    X = X.to(device)
    y = y.to(device)

    loss = module.Loss(model)
    loss_value = loss(X, y)
    if not state["eval"]:
        loss_value.backward()

    # Compute metrics here

    state["step_num"] += 1
    state["compute_time"].append(time.time() - start_time)
    state["loss"].append(loss_value.item())

    vis = visdom.Visdom(
        server=f"http://{state['master_url']}", 
        env="main", 
        use_incoming_socket=False
    )

    plots = []
    for filename in os.listdir(os.path.join(state["project_path"], "metrics")):
        metric_module = utils.get_module_name(filename)
        if metric_module:
            for f in im.import_module(f"metrics.{metric_module}").metrics:
                f(vis, state)

    


    server = f"http://{state['master_url']}:{state['port']}"
    if not state["eval"]:
        grads = collect(model)
        response = requests.post(server + "/update", data=pickle.dumps(grads))
        state["upload_time"].append(response.elapsed.total_seconds())
    else:
        state["upload_time"].append(0)
    
    requests.post(server + "/metrics", data=pickle.dumps(state))



def collect(model):
    return [param.grad for param in model.parameters()]


@click.command("worker")
@click.argument("project")
@click.option("--eval", is_flag=True)
@click.option('-c', '--config', help='config path', type=str)
def run(project, eval, config):
    project_path = os.path.join(ROOT_DIR, 'projects', project)
    env = os.path.join(project_path, "./env/bin/python")
    command = [
            env, __file__, project
        ]
    if eval:
        command += ["--eval"]
    if config is not None:
        command += ["-c", config]
    subprocess.call(command)


@click.command()
@click.argument("project")
@click.option("--eval", is_flag=True)
@click.option('-c', '--config', help='config path', type=str)
def worker(project, eval, config):
    global state
    state = {}

    project_path = os.path.join(ROOT_DIR, 'projects', project)
    sys.path.append(
        project_path
    )

    # loading project config
    project_config_path = os.path.join(project_path, 'config.json')
    with open(project_config_path, "r") as f:
        state.update(**json.load(f))

    server = f"http://{state['master_url']}:{state['port']}"

    worker_id, last_step, compute_time = requests.get(
        server + "/init",
        params=dict(pid=os.getpid()),
    ).json()

    state.update(
        worker_id=worker_id,
        project_path=project_path,
        step_num=0 if last_step is None else last_step,
        compute_time=[] if compute_time is None else [compute_time],
        download_time=[],
        upload_time=[],
        loss=[],
        eval=eval,
    )

    while True:
        try:
            logging.info("Downloading data")
            start = time.time()
            response = requests.get(server + "/pull")
            end = time.time()
        except requests.exceptions.ConnectionError as e:
            logging.info("Looks like master is unavailable")
            raise e
        logging.debug("Status %s", response.status_code)
        if response.status_code == 200:
            state["download_time"].append(end - start)
            model_state = pickle.loads(response.content)
            step(model_state)
        else:
            time.sleep(1)


if __name__ == "__main__":
    worker()

