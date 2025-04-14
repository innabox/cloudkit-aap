# Cloudkit Ansible Project

This repository contains the Ansible roles, playbooks, rulebooks, and
inventories that are used in the scope of cloudkit.

## Pre-requisites

This project uses uv to install Ansible and other Python dependencies.

Install all the necessary dependencies by running:

```
uv sync --all-groups
```

Then you can run commands like this:

```
uv run ansible-playbook ...
```

Or you can activate the virtual environment so all commands are in your `$PATH` by default:

```
source .venv/bin/activate
```

To install the Ansible collections required by the Ansible playbooks:

```
$ ansible-galaxy collection install -r collections/requirements.yml
```
