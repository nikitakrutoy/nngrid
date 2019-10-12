
from flask import Flask, request, Response, jsonify
from nngrid.constants import *

import importlib as im
import sys
import pickle
import torch.multiprocessing as mp
import logging
import os

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT, level="DEBUG")

sys.path.append(STATE["project_path"])

module = im.import_module('model')
model = module.Model()
model.share_memory()
opt = module.Opt(model.parameters(), **STATE["opt_config"])

app = Flask("updater")

@app.route("/")
def home():
    return "Succsess"

@app.route("/update", methods=["POST"])
def update():
    grads = pickle.loads(request.get_data())
    opt.zero_grad()
    for param, grad in zip(model.parameters(), grads):
        param.grad = grad
    opt.step()
    return Response(status=200)

@app.route("/take")
def take():
    worker_pid = request.args.get("pid")
    if not STATE.get(f"updater:{os.getpid()}"):
        STATE.set(f"updater:{os.getpid()}", worker_pid)
        return jsonify(False)
    else:
        return jsonify(True)

@app.route("/free")
def free():
    STATE.set(f"updater:{os.getpid()}", False)
    return Response(status=200)
    
print(STATE["port"], STATE["workers_num"])

ps = [
    mp.Process(
        name=f"{STATE['port'] - i}",
        target=app.run, 
        kwargs=dict(
            host="127.0.0.1",
            port=STATE["port"] - i,
        )
    ) for i in range(1, STATE["workers_num"] + 1)
]

for p in ps:
    p.start()
    logging.debug(f"Started {p}")
active_processes = set(ps)
print("Current active:", [_.pid for _ in active_processes])

while True:
    for p in active_processes:
        if not p.is_alive():
            logging.debug("f{p} died")
            port = p.name
            new_p = mp.Process(
                name=port,
                target=app.run, 
                kwargs=dict(
                    host="127.0.0.1",
                    port=int(port),
                )
            )
            new_p.start()
            worker_pid = STATE[f"updater:{p.pid}"]
            STATE.set(f"updater:{new_p.pid}", worker_pid)
            STATE.set(f"gunicorn-{worker_pid}-updater-port", new_p.pid)
            active_processes.add(new_p)
            logging.debug("f{new_p} created")
            print("Current active:", [_.pid for _ in active_processes])




