from nngrid.constants import *
import requests
import logging
import simplejson


def post_worker_init(worker):
    if STATE["mode"] == "hogwild":
        ports = list(range(STATE["port"] - 1, STATE["port"] - STATE["workers_num"] - 1, -1))
        logging.debug(str(ports))
        busy = True
        while True:
            for port in ports:
                try:
                    resp = requests.get(f"http://localhost:{port}/take", params=dict(pid=worker.pid))
                    # logging.debug(resp.content)
                    busy = resp.json()
                    if not busy:
                        STATE.set(f"gunicorn-{worker.pid}-updater-port", port)
                        logging.debug(f"{worker.pid} got conn with port {port}")
                        break
                except requests.exceptions.ConnectionError as e:
                    continue
                except simplejson.errors.JSONDecodeError:
                    continue
            if not busy:
                break

def worker_exit(server, worker):
    if STATE["mode"] == "hogwild":
        port = STATE[f"gunicorn-{worker.pid}-updater-port"]
        requests.get(f"http://localhost:{port}/free")