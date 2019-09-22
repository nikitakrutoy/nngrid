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
logging.basicConfig(level="INFO")


def step(model_state):
    start_time = time.time()

    module = im.import_module('model')
    model = module.Model()
    model.load_state_dict(model_state)

    dataset = module.DatasetClass(
        root_path=os.path.join(state["project_path"]),
    )

    batch_size = state["batch_size"]
    start = state["step_num"]
    X, y = dataset[start * batch_size: (start + 1) * batch_size]

    loss = module.Loss(model)
    loss_value = loss(X, y)
    loss_value.backward()

    # Compute metrics here

    state["step_num"] += 1
    state["compute_time"].append(time.time() - start_time)
    state["loss"].append(loss_value.item())

    # vis = visdom.Visdom(env="main", use_incoming_socket=False)

    # plots = []
    # for filename in os.listdir(os.path.join(state["project_path"], "metrics")):
    #     metric_module = utils.get_module_name(filename)
    #     if metric_module:
    #         plots.extend(im.import_module(f"metrics.{metric_module}").metrics)

    # for plot in plots:
    #     plot(vis, state)

    # del vis

    grads = collect(model)
    data = dict(
        grads=grads,
        worker_state=state,
    )

    server = f"http://{state['master_url']}:{state['port']}"

    requests.post(server + "/update", data=pickle.dumps(data))


def collect(model):
    return [param.grad for param in model.parameters()]


@click.command("worker")
@click.argument("project")
@click.option('-c', '--config', help='config path', type=str)
def run(project, config):
    project_path = os.path.join(ROOT_DIR, 'projects', project)
    env = os.path.join(project_path, "./env/bin/python")
    command = [
            env, __file__, project
        ]
    if config is not None:
        command += ["-c", config]
    subprocess.call(command)


@click.command()
@click.argument("project")
@click.option('-c', '--config', help='config path', type=str)
def worker(project, config):
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

    state["id"] = os.getpid() if state["master_url"] == "localhost" else str(requests.get(server + "/getid").content)

    state.update(
        project_path=project_path,
        step_num=0,
        compute_time=[],
        loss=[],
    )
    server = f"http://{state['master_url']}:{state['port']}"

    while True:
        try:
            response = requests.get(state["master_url"] + "/pull")
            response = requests.get(server + "/pull")
        except requests.exceptions.ConnectionError as e:
            logging.info("Looks like master is unavailable")
            raise e

        if response.status_code == 200:
            model_state = pickle.loads(response.content)
            step(model_state)
        else:
            time.sleep(1)


if __name__ == "__main__":
    worker()

