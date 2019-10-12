import redis
import json
import os
import click
import subprocess
import shutil
import psycopg2

import logging

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT, level="DEBUG")


def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        print(stdout_line, end="")
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


class State(redis.Redis):
    def set(self, key, value, ex=None, px=None, nx=False, xx=False):
        key = "nngrid:{key}".format(key=key)
        value = json.dumps(value)
        return super().set(key, value, ex=ex, px=px, nx=nx, xx=xx)

    def get(self, key):
        s = super().get("nngrid:{key}".format(key=key))
        return json.loads(s) if s is not None else s

    def mset(self, mapping):
        return super().mset({
            "nngrid:{key}".format(key=key): json.dumps(value)
            for key, value in mapping.items()
        })


class PostgressMetricsConnector:
    def __init__(self, host):
        self.conn = psycopg2.connect(
            f"dbname='postgres' user='postgres' host='{host}' password='docker'"
        )
        self.query = \
            "INSERT INTO data " \
            "VALUES (%(worker_id)s, %(run_id)s, %(step_num)s, %(loss)s, %(compute_time)s, %(download_time)s, %(upload_time)s, CURRENT_TIMESTAMP, %(eval)s)"

    def insert(self, data):
        cur = self.conn.cursor()
        cur.execute(
            self.query,
            data
        )
        self.conn.commit()
        cur.close()
    
    def fetchone(self, query):
        cur = self.conn.cursor()
        cur.execute(query)
        result = cur.fetchone()
        cur.close()
        return result


class ExpandedPath(click.Path):
    def convert(self, value, *args, **kwargs):
        value = os.path.expanduser(value)
        return super(ExpandedPath, self).convert(value, *args, **kwargs)


def get_module_name(filename):
    if '.py' not in filename or '__' in filename:
        return None
    else:
        return filename.split(".")[0]

def nukedir(dir):
    shutil.rmtree(dir, ignore_errors=True)
