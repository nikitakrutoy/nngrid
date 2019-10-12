from celery import Celery
from torch.utils.data import DataLoader
from numpy.random import randint

import importlib as im


import torch
import pickle
import requests
import nngrid.utils as utils
import visdom
import time
import sys
import io
import logging
import binascii
from hashlib import md5

from filelock import Timeout, FileLock

from nngrid.constants import *
from nngrid.constants import STATE
from nngrid.utils import PostgressMetricsConnector


logging.getLogger("filelock").setLevel(logging.WARNING)

celery = Celery(
    'nngrid.tasks', 
    backend='db+sqlite:///db.sqlite',
    broker='redis://localhost:6379'
)

def aggregate(updates):
    logging.info("Aggregating, " + STATE["status"])
    result = None
    for i, update in enumerate(updates):
        with open(f"{UPDATES_DIR}/{update}", "rb") as f:
            if i == 0:
                result = pickle.load(f)
            else:
                grad = pickle.load(f)
                for nth_params in range(len(result)):
                    result[nth_params] += grad[nth_params]

    return result


def apply(grads):
    # LOAD
    sys.path.append(STATE["project_path"])
    states_dir = os.path.join(STATE["project_path"], "states",)

    model_state_path = os.path.join(states_dir, "model_state.torch")
    opt_state_path = os.path.join(states_dir, "opt_state.torch")
    lock_path = os.path.join(states_dir, "lock")

    module = im.import_module('model')
    lock = FileLock(lock_path, timeout=-1)

    with lock.acquire(poll_intervall=POLL_INTERVAL) as lock:

        model = module.Model(**STATE["model_config"])
        if os.path.isfile(model_state_path):
            model.load_state_dict(torch.load(model_state_path))

        opt = module.Opt(model.parameters(), **STATE["opt_config"])
        if os.path.isfile(opt_state_path):
            opt.load_state_dict(torch.load(opt_state_path))

        # APPLY
        opt.zero_grad()
        for param, grad in zip(model.parameters(), grads):
            param.grad = grad
        opt.step()

        

        if not os.path.exists(states_dir):
            os.mkdir(states_dir)

        # SAVE
        torch.save(model.state_dict(), model_state_path)
        torch.save(opt.state_dict(), opt_state_path)


@celery.task
def lr_change(lr):
    sys.path.append(STATE["project_path"])
    states_dir = os.path.join(STATE["project_path"], "states",)
    lock_path = os.path.join(states_dir, "lock")
    lock = FileLock(lock_path, timeout=-1)
    with  lock.acquire(poll_intervall=POLL_INTERVAL):
        opt_state_path = os.path.join(states_dir, "opt_state.torch")
        model_state_path = os.path.join(states_dir, "model_state.torch")
        module = im.import_module('model')

        model = module.Model(**STATE["model_config"])
        if os.path.isfile(model_state_path):
            model.load_state_dict(torch.load(model_state_path))

        opt = module.Opt(model.parameters(), **STATE["opt_config"])
        if os.path.isfile(opt_state_path):
            opt.load_state_dict(torch.load(opt_state_path))

        for g in opt.param_groups:
            g['lr'] = lr

        torch.save(opt.state_dict(), opt_state_path)
        

@celery.task
def metrics(data):
    db = PostgressMetricsConnector("localhost")
    data = pickle.loads(binascii.a2b_base64(data))
    data.update(
            run_id=STATE['run_id'],
            loss=data["loss"][-1],
            download_time=data["download_time"][-1],
            upload_time=data["upload_time"][-1],
            compute_time=data["compute_time"][-1],
        )
    db.insert(data)
    db.conn.close()

@celery.task
def update(data):
    if STATE['mode'] == 'sync':
        file_hash = md5(data).hexdigest()
        states_dir = os.path.join(STATE["project_path"], "states",)
        lock_path = os.path.join(states_dir, "lock")
        lock = FileLock(lock_path, timeout=-1)
        with  lock.acquire(poll_intervall=POLL_INTERVAL):
            with open(f"{UPDATES_DIR}/update_{file_hash}", "wb") as f:
                f.write(data)
            updates = os.listdir(UPDATES_DIR)
        logging.debug(updates)
        if len(updates) == STATE["workers_num"]:
            grads = aggregate(updates)
            apply(grads)
            for item in updates:
                os.remove(f"{UPDATES_DIR}/{item}")
            STATE["status"] = "serving"

    if STATE['mode'] == 'async':
        grads = pickle.loads(data)
        apply(grads)