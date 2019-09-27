#! /usr/bin/env python

import click
import nngrid.modules.master as master
import nngrid.modules.worker as worker
import nngrid.modules.control as control
from nngrid.modules.clone import clone

import os


@click.group()
def main():
    if not os.path.isdir(os.path.expanduser("~/.nngrid")):
        os.makedirs(os.path.expanduser("~/.nngrid/projects"))
        os.makedirs(os.path.expanduser("~/.nngrid/configs"))
        os.makedirs(os.path.expanduser("~/.nngrid/updates"))


main.add_command(master.run)
main.add_command(worker.run)
main.add_command(control.run)
main.add_command(clone)


if __name__ == "__main__":
    main()
