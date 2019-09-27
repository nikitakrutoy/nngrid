import redis
import json
import os
import click
import subprocess
import shutil

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
        return json.loads(super().get("nngrid:{key}".format(key=key)))

    def mset(self, mapping):
        return super().mset({
            "nngrid:{key}".format(key=key): json.dumps(value)
            for key, value in mapping.items()
        })


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