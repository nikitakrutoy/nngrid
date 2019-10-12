import os
from nngrid.utils import State
from redis import Redis

ROOT_DIR = os.path.expanduser("~/.nngrid")
UPDATES_DIR = f"{ROOT_DIR}/updates"
STATE = State(host='localhost', port=6379, db=13, decode_responses=True)
REDIS = Redis(host='localhost', port=6379, db=12)

POLL_INTERVAL=0.0001
REDIS_LOCK_KWARGS = dict()
FILE_LOCK_KWARGS = dict(poll_interval=POLL_INTERVAL)
DEFAULT_MASTER_CONFIG = {}
DEFAULT_WORKER_CONFIG = {}
