import git
import click
import logging
import argparse
import os
import subprocess
import nngrid.utils as utils
ROOT_PATH = os.path.expanduser("~/")


def extract_project_name(git_url):
    *_, user_name, repo_name = git_url.split("/")
    repo_name, _ = repo_name.split(".")
    return f"{user_name}-{repo_name}"


class Progress(git.remote.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        logging.info(self._cur_line)


@click.command()
@click.argument("git_repo_url")
def clone(git_repo_url, project_name=None):
    project_name = project_name if project_name is not None else extract_project_name(git_repo_url)
    project_path = os.path.join(ROOT_PATH, ".nngrid/projects", project_name)
    utils.nukedir(project_path)
    git.Repo.clone_from(git_repo_url, project_path, progress=Progress())
    logging.info("Cloned")

    # Installing virtualenv
    command = [
            "virtualenv", os.path.join(project_path, "env"), 
            "--system-site-packages",
            "--python=python3"
    ]
    utils.execute(command)
    logging.info("Installed venv")

    # Installing dependencies
    command = [
            os.path.join(project_path, "env/bin/pip3"), 
            "install", 
            "-r", os.path.join(project_path, "requirements.txt"),
    ]
    utils.execute(command)
    logging.info("Installed dependecies")


def run(agrs_list):
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="github url",)
    args = parser.parse_args((agrs_list))
    clone(args.url)
