import os
from nngrid.utils import State

ROOT_DIR = os.path.expanduser("~/.nngrid")
UPDATES_DIR = f"{ROOT_DIR}/updates"
STATE = State(host='localhost', port=6379, db=13, decode_responses=True)

POLL_INTERVAL=0.0001
DEFAULT_MASTER_CONFIG = {}
DEFAULT_WORKER_CONFIG = {}
